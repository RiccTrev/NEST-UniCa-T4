from pyomo.environ import *
from pyomo.core.expr import Expr_if
import pandas as pd
import parametri
import numpy as np
import random

def optimize_consumer_milp(min_demand, max_demand, injection, residual_load):

    def get_element_from_list(my_list):
        result = {}
        for i, element in enumerate(my_list):
            result[i] = element
        return result

    # Sample Data
    #d_min_values = {0: 5, 1: 4, 2: 6, 3: 2, 4: 5}
    #d_max_values = {0: 7, 1: 5, 2: 10, 3: 5, 4: 5}
    #injected_from_prosumer = {0: 10, 1: 5, 2: 7, 3: 3, 4: 4}
    #initial_SOC = 0
    #SOC_min = 0
    #SOC_max = 0
    #delta_charge_max = 0
    #eta = 1
    #Delta_t = 1
    #C_buy = 0.10
    #C_sell = 0.05
    #incentive = 0.12
    #bigM = 1000  # This should be set to a large enough value, based on the context of your problem
    #model = ConcreteModel()
    T = range(len(min_demand))
    d_min_values = get_element_from_list(min_demand)
    d_max_values = get_element_from_list(max_demand)
    injected_from_prosumer = get_element_from_list(injection)
    residual_load = get_element_from_list(residual_load)
    Delta_t = 1
    C_buy = parametri.C_buy
    C_sell = parametri.C_sell
    bigM = 1000  # Not in use in this model
    
    model = ConcreteModel()

    # Parameters
    model.T = Set(initialize=T)
    model.C_buy = Param(initialize=C_buy)
    model.C_sell = Param(initialize=C_sell)
    model.P_load_min = Param(model.T, initialize=d_min_values, within = Reals)
    model.P_load_max = Param(model.T, initialize=d_max_values, within = Reals)
    model.P_gen = Param(model.T, initialize=injected_from_prosumer)
    model.residual_load = Param(model.T, initialize=residual_load)
    

    # Decision Variables
    def P_load_bounds(model, t):
        return (model.P_load_min[t], model.P_load_max[t])

    # Variables
    model.P_load = Var(model.T, within=NonNegativeReals, bounds=P_load_bounds)
    model.P_grid = Var(model.T, domain=Reals) #Net exchanges with grid (positive buy, negative sell)
    model.VarDiff = Var(model.T, domain=Reals)  # Variable for the difference between Var1 and Var2
    model.AbsDiff = Var(model.T, within=NonNegativeReals)  # Variable for the absolute value of the difference

    #F.O. Maximize shared energy (as the abs of the difference of P_load and P_gen)
    def objective_rule(model): 
        return sum(model.AbsDiff[t] for t in T)
    model.objective = Objective(rule = objective_rule, sense = minimize)

    # Define Constraints
    #Energy balance (I need residual load to account for the load of the prosumers as residual load): 
    def energy_balance(model, t): 
    #    return model.P_load[t] == model.P_gen[t] - model.residual_load[t] # + model.P_grid[t] 
        return model.P_load[t] ==  model.P_grid[t] + model.P_gen[t] - model.residual_load[t]

    model.energy_balance = Constraint(model.T, rule=energy_balance)
  
    def constraint_var_diff(model, t): 
        return model.VarDiff[t] == model.P_load[t] - model.P_gen[t] + model.residual_load[t]
    model.constraint_var_diff = Constraint(model.T, rule=constraint_var_diff)

    def const_abs1(model, t): 
        return model.AbsDiff[t] >= model.VarDiff[t]
    model.const_abs1 = Constraint(model.T, rule=const_abs1)

    def const_abs2(model, t): 
        return model.AbsDiff[t] >= -model.VarDiff[t]
    model.const_abs2 = Constraint(model.T, rule=const_abs2)


    # Solve the model
    solver = SolverFactory('glpk', executable = 'C:\glpk\w64\glpsol.exe') 
    #solver = SolverFactory('ipopt', executable='C:\\ipopt\\bin\\ipopt.exe')
    #TransformationFactory('gdp.bigm').apply_to(model)
    solver.solve(model)#, tee = True)

    ## Print the results
    #print("\n--- Consumer Optimization Results ---\n")
    #model.display()
    #for t in model.T:
    #    print(f"At time {t}, AbsDiff: {model.AbsDiff[t]()}, Injection: {model.P_gen[t]}, Consumer load: {model.P_load[t]()}, Prosumer residual load: {model.residual_load[t]}, P_grid: {model.P_grid[t]()}")
    # Initialize empty lists for each decision variable you want to save
    P_load_array = np.array([value(model.P_load[t]()) for t in model.T])
    Shared_array = np.array([min(value(model.P_load[t]) + value(model.residual_load[t]), value(model.P_gen[t])) for t in model.T])
    best_sol_parameters = {
        'shared': Shared_array,
        "consumer_load": P_load_array,
        'residual_prosumers_load': np.array(residual_load)
    }
    return pd.DataFrame(best_sol_parameters)



#fake call to test
#optimize_consumer_milp(random.sample(range(1, 30), 4), random.sample(range(30, 50), 4), random.sample(range(1, 50), 4), random.sample(range(1, 50), 4))
#optimize_consumer_milp([0,0,0,0],[4,5,6,7], [5,4,6,8], [1,2,5,3])
