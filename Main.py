import ProsumerModel as pyp
import ConsumerModel as pyc
import numpy as np
import pandas as pd
from pathlib import Path
import os
#import sys
#sys.path.append('../')
import pprint
import functions
import parametri
import warnings
import pprint
import json

# Ignore specific category of warning
warnings.simplefilter(action='ignore', category=FutureWarning)

input_directory = 'C:/Users/trevi/Dropbox/@Trevisan-Ghiani/WIP/PES 2024/PyGAD/Input Files/'
output_directory = 'C:/Users/trevi/Dropbox/@Trevisan-Ghiani/WIP/PES 2024/PyOmo/Output Files/'

#Set Seed for results replicability
np.random.seed(0)

def main():
    try:
        fn = input_directory + 'PUN_2021_Aggiustato.xlsx'
        xl = pd.ExcelFile(fn)
        xl.sheet_names
        # Creo un dizionario di DataFrame.
        dfs = {sh: xl.parse(sh, header=0) for sh in xl.sheet_names}
        # Stampo le chiavi del dizionario (nomi dei workspace di excel)
        dfs.keys()
        df_prezzi = dfs['Prezzi-Prices']
    except:
        raise TypeError('Non sono riuscito ad aprire il file.')

    PUN = np.array(df_prezzi['PUN'] / 1000)
    #print(len(PUN))

    # Open excel data file with users information (prosumers/consumers, consumption & production data).
    try:
        fn = input_directory + 'Input_GA.xlsx'
        xl = pd.ExcelFile(fn)
        xl.sheet_names
    except:
        raise TypeError('Non sono riuscito ad aprire il file.')
    # Create df dictionary.
    dfs = {sh: xl.parse(sh, header=0) for sh in xl.sheet_names}
    # Stampo le chiavi del dizionario (nomi dei workspace di excel)
    #print(dfs.keys())
    # Set the window for the optimization: ottimizzazione per una giornata a granularità quartoraria. 
    window = 96
    #Parameter for the Monte Carlo simulation: N is the number of simulations that are realized. Each forecasted load curve is sampled N times.
    N = 10
    #Dict that contains the results of the simulation: it's a dict that contains a dict that contains data frames. 
    #First dict index: number of simulation
    #Second dict index: users
    dfs_sol = {}
    list_prosumers = dfs['Info'][dfs['Info']['Category'] == 'Prosumer']['Users'].to_list()
    list_utenti = dfs['Info'][dfs['Info']['Category'] == 'Prosumer']['Users'].to_list()
    list_utenti.append('Aggregated')
    #Iterate over N
    for i in range(N): 
        if i%10 == 0: 
            print(f'Iterazione numero: {i}')    
        dfs_sol[i] = {}
        #For each Monte Carlo Simulation optimize the prosumer
        for prosumer in list_prosumers:  
            #print(f"UTENTE:  {prosumer}")
            dfs_sol[i][prosumer] = {}
            min_demand = np.random.normal(loc=dfs[prosumer]['MinCons'], scale=0.15, size=len(dfs[prosumer]['MinCons']))
            max_demand = np.random.normal(loc=dfs[prosumer]['MaxCons'], scale=0.15, size=len(dfs[prosumer]['MaxCons']))
            # Ensure min_demand and max_demand are not less than zero
            min_demand = np.maximum(min_demand, 0)
            max_demand = np.maximum(max_demand, 0)
            # Ensure min_demand is not greater than max_demand
            min_demand = np.minimum(min_demand, max_demand)
            pv_production = np.array(dfs[prosumer]['Production'])
            max_battery_capacity = int(dfs['Info'][dfs['Info']['Users'] == prosumer]['BatteryCapacity'].iloc[0])
            for j in range(0, np.array(dfs[prosumer]['MaxCons']).size, window):  # slice arrays every window items
                if j == 0:
                    initial_soc = 0.0  # the battery is empty the first time slot
                else:  # get last soc of the day before
                    initial_soc = float(dfs_sol[i][prosumer]['df']['battery_energy'].iloc[-1])
                min_demand_chunk = min_demand[j:j + window]
                max_demand_chunk = max_demand[j:j + window]
                pv_production_chunk = pv_production[j:j + window]
                # Call optimizer instance
                df_dictionary = pyp.optimize_prosumer_milp(min_demand_chunk, max_demand_chunk, pv_production_chunk, max_battery_capacity, initial_soc)
                # append the solution dictionary to the user data frame
                if 'df' not in dfs_sol[i][prosumer]:
                    dfs_sol[i][prosumer] = pd.DataFrame()
                dfs_sol[i][prosumer] = pd.concat([dfs_sol[i][prosumer], df_dictionary])
            # Add production and DataOra columns
            dfs_sol[i][prosumer].insert(0, 'DataOra', dfs[prosumer]['Time'].tolist())
            dfs_sol[i][prosumer].insert(1, 'Production', pv_production.tolist())
        
        # After prosumer optimization it's the aggregated consumers' turn
        
        # Iterate over the dictionary of dataframes to calculate injection and residual load of prosumers'
        for prosumer in list_prosumers:
            #Declare required arrays
            injection = np.zeros_like(np.array(dfs_sol[i][prosumer]['DataOra']), dtype=float)
            residual_load = np.zeros_like(np.array(dfs_sol[i][prosumer]['DataOra']), dtype=float)
            #Update required arrays with corresponding injection and residual load data of the i-th simulation
            injection += np.array(dfs_sol[i][prosumer]['grid_energy'].apply(lambda x: x if x > 0 else 0))  # these terms are > 0
            residual_load += np.array(dfs_sol[i][prosumer]['grid_energy'].apply(lambda x: -x if x < 0 else 0))  # these terms are < 0
        
        # Monte Carlo for min and max demand of aggregated consumers.
        # calculate min and max demand arrays for the aggregated consumers
        min_consumer_demand = np.random.normal(loc=dfs['Aggregated']['MinCons'], scale=0.15, size=len(dfs['Aggregated']['MinCons']))
        max_consumer_demand = np.random.normal(loc=dfs['Aggregated']['MaxCons'], scale=0.15, size=len(dfs['Aggregated']['MaxCons']))
        # Ensure min_demand and max_demand are not less than zero
        min_consumer_demand = np.maximum(min_consumer_demand, 0)
        max_consumer_demand = np.maximum(max_consumer_demand, 0)
        # Ensure min_demand is not greater than max_demand
        min_consumer_demand = np.minimum(min_consumer_demand, max_consumer_demand)
        # Declare dict for the aggregated consumer i-th optimization
        #pprint.pprint(dfs_sol)
        dfs_sol[i]['Aggregated'] = pd.DataFrame()

        #Optimize consumer chunk
        for j in range(0, np.array(dfs['Aggregated']['MaxCons']).size, window):  # slice arrays every delta time items
            min_consumer_demand_chunk = min_consumer_demand[j:j + window]
            max_consumer_demand_chunk = max_consumer_demand[j:j + window]
            injected_chunk = injection[j:j + window]
            residual_load_chunk = residual_load[j:j + window]
            # append the solution dictionary to the user data frame
            optimized_consumers = pyc.optimize_consumer_milp(min_consumer_demand_chunk, max_consumer_demand_chunk, injected_chunk, residual_load_chunk)
            dfs_sol[i]['Aggregated'] = pd.concat([dfs_sol[i]['Aggregated'], optimized_consumers])
        # Insert DataOra and Injection Columns
        dfs_sol[i]['Aggregated'].insert(0, 'DataOra', dfs_sol[i][prosumer]['DataOra'])
        dfs_sol[i]['Aggregated'].insert(1, 'Injection', injection)

        # Rename columns and calculate Immissione, Prelievo, P and Autoconsumo
        #list_utenti = list(dfs_sol[i].keys()).remove('comunita')
        #print(f'LISTA UTENTI CHE SONO STATI OTTIMIZZATI: {list_utenti}')
        for membro in list_utenti:
            if membro == 'Aggregated':
                dfs_sol[i][membro] = dfs_sol[i][membro].rename(
                    columns={'consumer_load': 'Prelievo', 'Injection': 'ImmissioneProsumers',
                             'residual_prosumers_load': 'CaricoResiduoProsumers', 'shared': 'Condivisa'})
                dfs_sol[i][membro]['Immissione'] = 0
                dfs_sol[i][membro]['P'] = 0
                dfs_sol[i][membro]['Autoconsumo'] = 0
                # dfs_sol[membro]['SOC'] = 0
            if membro != 'Aggregated':
                dfs_sol[i][membro] = dfs_sol[i][membro].rename(
                    columns={'Production': 'P', 'self_consumption': 'Autoconsumo',
                             'battery_energy': 'SOC', 'Load': 'ConsumoTotale', 'grid_energy': 'PrelievoImmissioneRete'})
                dfs_sol[i][membro]['Immissione'] = dfs_sol[i][membro]['PrelievoImmissioneRete'].apply(lambda x: x if x > 0 else 0)
                dfs_sol[i][membro]['Prelievo'] = dfs_sol[i][membro]['PrelievoImmissioneRete'].apply(lambda x: -x if x < 0 else 0)
        
        # Realizzo df comunita
        dfs_sol[i]['comunita'] = pd.DataFrame(
            columns=['Consumption', 'P', 'Autoconsumo', 'Immissione', 'Prelievo', 'MateriaEnergia', 'TrasportoEGestione',
                     'Imposte', 'CostoBolletta', 'RID',
                     'RisparmioDaAutoconsumo'])  # Condivisa, EntrateCondivisa, RestituzioneComponentiTariffarieEntrateTotali
        dfs_sol[i]['comunita']['DataOra'] = dfs_sol[i][prosumer]['DataOra']
        dfs_sol[i]['comunita']['Month'] = dfs_sol[i]['comunita']['DataOra'].dt.month
        dfs_sol[i]['comunita']['Day'] = dfs_sol[i]['comunita']['DataOra'].dt.day
        dfs_sol[i]['comunita']['Hour'] = dfs_sol[i]['comunita']['DataOra'].dt.hour
        dfs_sol[i]['comunita']['DayOfWeek'] = dfs_sol[i]['comunita']['DataOra'].dt.dayofweek
        dfs_sol[i]['comunita'] = dfs_sol[i]['comunita'].fillna(0)
        
        #Calcolo a livello comunità di Consumo, Produzione (P), Autoconsumo, Immissione in rete, Prelievo dalla rete. Necessito differenziare fra consumer ('Aggregated') e prosumers. 
        for membro in list_utenti:
            #print(f'il membro è: {membro}')
            # Consumption: inteso come consumo totale:
            if membro != 'Aggregated':
                dfs_sol[i]['comunita']['Consumption'] = dfs_sol[i]['comunita']['Consumption'] + dfs_sol[i][membro]['ConsumoTotale']
                dfs_sol[i]['comunita']['P'] = dfs_sol[i]['comunita']['P'] + dfs_sol[i][membro]['P']
                dfs_sol[i]['comunita']['Autoconsumo'] = dfs_sol[i]['comunita']['Autoconsumo'] + dfs_sol[i][membro]['Autoconsumo']
                dfs_sol[i]['comunita']['Immissione'] = dfs_sol[i]['comunita']['Immissione'] + dfs_sol[i][membro]['Immissione']
                dfs_sol[i]['comunita']['Prelievo'] = dfs_sol[i]['comunita']['Prelievo'] + dfs_sol[i][membro]['Prelievo']
            else:
                dfs_sol[i]['comunita']['Consumption'] = dfs_sol[i]['comunita']['Consumption'] + dfs_sol[i][membro]['Prelievo']
                dfs_sol[i]['comunita']['P'] = dfs_sol[i]['comunita']['P'] + dfs_sol[i][membro]['P']
                dfs_sol[i]['comunita']['Autoconsumo'] = dfs_sol[i]['comunita']['Autoconsumo'] + dfs_sol[i][membro]['Autoconsumo']
                dfs_sol[i]['comunita']['Prelievo'] = dfs_sol[i]['comunita']['Prelievo'] + dfs_sol[i][membro]['Prelievo']

            functions.CalcolaCostiERisparmiUtente(dfs_sol[i][membro],PUN)  # Calcola MateriaEnergia, TrasportoEGestione, Imposte, CostoBolletta, RID, RisparmioDaAutoconsumo
            dfs_sol[i]['comunita']['MateriaEnergia'] = dfs_sol[i]['comunita']['MateriaEnergia'] + dfs_sol[i][membro]['MateriaEnergia']
            dfs_sol[i]['comunita']['TrasportoEGestione'] = dfs_sol[i]['comunita']['TrasportoEGestione'] + dfs_sol[i][membro]['TrasportoEGestione']
            dfs_sol[i]['comunita']['Imposte'] = dfs_sol[i]['comunita']['Imposte'] + dfs_sol[i][membro]['Imposte']
            dfs_sol[i]['comunita']['CostoBolletta'] = dfs_sol[i]['comunita']['CostoBolletta'] + dfs_sol[i][membro]['CostoBolletta']
            dfs_sol[i]['comunita']['RID'] = dfs_sol[i]['comunita']['RID'] + dfs_sol[i][membro]['RID']
            dfs_sol[i]['comunita']['RisparmioDaAutoconsumo'] = dfs_sol[i]['comunita']['RisparmioDaAutoconsumo'] + dfs_sol[i][membro]['RisparmioDaAutoconsumo']

        potenza_totale = 0
        potenza_totale = sum(dfs['Info']['PV'])
        dfs_sol[i]['comunita']['PUN'] = PUN
        dfs_sol[i]['comunita']['Condivisa'] = dfs_sol[i][membro]['Condivisa']
        dfs_sol[i]['comunita']['EntrateCondivisa'] = dfs_sol[i]['comunita'].apply(lambda x: functions.CalcolaIncentiviMASE(x['Condivisa'], x['PUN'], potenza_totale), axis=1)
        dfs_sol[i]['comunita']['RestituzioneComponentiTariffarie'] = dfs_sol[i]['comunita']['Condivisa'] * parametri.incentivi['RestituzioneComponentiTariffarie']
        dfs_sol[i]['comunita']['EntrateTotali'] = dfs_sol[i]['comunita']['EntrateCondivisa'] + dfs_sol[i]['comunita']['RestituzioneComponentiTariffarie'] + dfs_sol[i]['comunita']['RID']
        dfs_sol[i]['comunita_mensile'] = dfs_sol[i]['comunita'].resample('M', on='DataOra').sum().drop(columns=['Month', 'Day', 'Hour', 'DayOfWeek', 'PUN']).reset_index()
        dfs_sol[i]['comunita_annuale'] = dfs_sol[i]['comunita'].resample('Y', on='DataOra').sum().drop(columns=['Month', 'Day', 'Hour', 'DayOfWeek', 'PUN']).reset_index()

    print("##########Scrittura dei file in output##########")
    solutions_dict = {}
    for membro in dfs_sol[i].keys():
        solutions_dict[membro] = {}
        #print(f'Scrivo il file per: {membro}')
        try:
            file = Path(output_directory + 'output_user'+membro+'.xlsx')
            if file.exists():
                #print("Il file esiste già. Elimino quello vecchio.")
                os.remove(file)
            with pd.ExcelWriter(output_directory + 'output_user'+membro+'.xlsx') as writer:
                for i in range(N):     
                    dfs_sol[i][membro].to_excel(writer, index=False, sheet_name=f'{membro}_sim_{i}')
                    solutions_dict[membro][i] = dfs_sol[i][membro].to_json(orient="records")
        except:
            raise TypeError('Impossibile scrivere il file, verificare che non sia già aperto e riprovare.')
    
    solutions_dict = {membro: {i: json.loads(json_str) for i, json_str in data.items()} for membro, data in solutions_dict.items()}

    with open('solutions.json', 'w') as f:
        json.dump(solutions_dict, f, indent=4)

    #Calculate scores (fitness function for each user and for each simulation)
    print('Scrivo file ff')
    #try: 
    file = Path(output_directory + 'fitness' + '.xlsx')
    if file.exists():
        #print('Il file esiste già. Elimino quello vecchio.')
        os.remove(file)
        #ff_df = pd.DataFrame(columns=['Iter', 'User', 'Category', 'ff'])
        ff_complete_df = pd.DataFrame(columns=['Iter', 'User', 'Category', 'ff'])
        ff_dict = {}
    with pd.ExcelWriter(output_directory + 'fitness' + '.xlsx') as writer:
        # calcolo la ff per i prosumer
        for i in range(N):
            #save the iteration number
            ff_dict[i] = {}
            ff_df = pd.DataFrame(columns=['Iter', 'User', 'Category', 'ff'])
            
            for prosumer in list_prosumers:
                ff_dict[i][prosumer] = {'Category': 'Prosumer', 'ff': np.sum(-(dfs_sol[i][prosumer]['ConsumoTotale'].to_numpy() - dfs_sol[i][prosumer]['Autoconsumo']))}
                
                new_row = pd.DataFrame([{'Iter': i, 'User': prosumer, 'Category': 'Prosumer', 'ff': np.sum(-(dfs_sol[i][prosumer]['ConsumoTotale'].to_numpy() - dfs_sol[i][prosumer]['Autoconsumo']))}])
                ff_df = pd.concat([ff_df, new_row], ignore_index=True)
                ff_complete_df = pd.concat([ff_complete_df, new_row], ignore_index=True)

            ff_dict[i]['Aggregated'] = {'Category': 'Aggregated','ff': np.sum(dfs_sol[i]['Aggregated']['Condivisa'])}
            new_row = pd.DataFrame([{'Iter': i, 'User': 'Aggregated', 'Category': 'Aggregated','ff': np.sum(dfs_sol[i]['Aggregated']['Condivisa'])}])
            # Filter out columns where all elements are NA
            ff_df = ff_df.dropna(axis=1, how='all')
            new_row = new_row.dropna(axis=1, how='all')
            ff_df = pd.concat([ff_df, new_row], ignore_index=True)
            ff_complete_df = pd.concat([ff_complete_df, new_row], ignore_index=True)
            ff_df.to_excel(writer, index=False, sheet_name=f'sim_{i}')
    with pd.ExcelWriter(output_directory +'final_complete_ff.xlsx') as writer: 
        ff_complete_df.to_excel(writer, index=False, sheet_name=f'ff_complete_df')
        # Syntax of write JSON data to file

    with open('fitness.json', 'w') as f:
        json_str = json.dumps(ff_dict)
        f.write(json_str)
    #except:
    #    raise TypeError('Impossibile scrivere il file, verificare che non sia già aperto e riprovare.')
    #pprint.pprint(dfs_sol, indent =4, compact = True)
    #print(f'Keys: {dfs_sol.keys()}')
    #print(f'elements of a simulation: {dfs_sol[0].keys()}')
    #print(f'elements in a single file: \n')
    #print(f'WC30-64 (prosumer): {dfs_sol[0]["WC30-64"]}')
    #print(f'Aggregated consumers: {dfs_sol[0]["Aggregated"]}')
    #print(f'community (annual): {dfs_sol[0]["comunita_annuale"]}')

if __name__ == "__main__":
    main()



"""if file.exists():
        #print('Il file esiste già. Elimino quello vecchio.')
        os.remove(file)
        #ff_df = pd.DataFrame(columns=['Iter', 'User', 'Category', 'ff'])
        ff_complete_df = pd.DataFrame(columns=['Iter', 'User', 'Category', 'ff'])
        dict_df = {}
    with pd.ExcelWriter(output_directory + 'fitness' + '.xlsx') as writer:
        # calcolo la ff per i prosumer
        for i in range(N):
            #save the iteration number
            dict_df[i] = i
            ff_df = pd.DataFrame(columns=['Iter', 'User', 'Category', 'ff'])
            for prosumer in list_prosumers:
                new_row = pd.DataFrame([{'Iter': i, 'User': prosumer, 'Category': 'Prosumer', 'ff': np.sum(-(dfs_sol[i][prosumer]['ConsumoTotale'].to_numpy() - dfs_sol[i][prosumer]['Autoconsumo']))}])
                ff_df = pd.concat([ff_df, new_row], ignore_index=True)
                ff_complete_df = pd.concat([ff_complete_df, new_row], ignore_index=True)
            new_row = pd.DataFrame([{'Iter': i, 'User': 'Aggregated', 'Category': 'Aggregated','ff': np.sum(dfs_sol[i]['Aggregated']['Condivisa'])}])
            # Filter out columns where all elements are NA
            ff_df = ff_df.dropna(axis=1, how='all')
            new_row = new_row.dropna(axis=1, how='all')
            ff_df = pd.concat([ff_df, new_row], ignore_index=True)
            ff_complete_df = pd.concat([ff_complete_df, new_row], ignore_index=True)
            ff_df.to_excel(writer, index=False, sheet_name=f'sim_{i}')
        print(ff_df)
    with pd.ExcelWriter(output_directory +'final_complete_ff.xlsx') as writer: 
        ff_complete_df.to_excel(writer, index=False, sheet_name=f'ff_complete_df')"""