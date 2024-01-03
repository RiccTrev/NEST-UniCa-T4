from pyomo.environ import *
from pyomo.core.expr import Expr_if
import pandas as pd
import parametri
import numpy as np

def optimize_prosumer_milp(min_demand, max_demand, pv_production, max_battery_capacity, initial_soc, delta_charge_max = 1000000): 
        
    #I need to put elements in dictionary (Pyomo works with dictionary)
    def get_element_from_list(my_list):
        result = {}
        for i, element in enumerate(my_list):
            result[i] = element
        return result

    # Sample Data
    #d_min_values = {0: 5, 1: 4, 2: 8, 3: 2, 4: 1}
    #d_max_values = {0: 7, 1: 5, 2: 10, 3: 5, 4: 5}
    #production_values = {0: 2, 1: 2, 2: 2, 3: 2, 4: 2}
    #initial_SOC = 0
    #SOC_min = 0
    #SOC_max = 10
    #delta_charge_max = 5
    #eta = 1
    #Delta_t = 1
    #bigM = 1000  # This should be set to a large enough value, based on the context of your problem

    T = range(len(min_demand))
    d_min_values = get_element_from_list(min_demand)
    d_max_values = get_element_from_list(max_demand)
    production_values = get_element_from_list(pv_production)
    initial_SOC = initial_soc
    SOC_max = max_battery_capacity
    SOC_min = 0
    Delta_t = 0
    eta = 1
    bigM = 1000  # This should be set to a large enough value, based on the context of your problem
    C_buy = parametri.C_buy
    C_sell = parametri.C_sell
    model = ConcreteModel()

    # Parameters
    model.T = Set(initialize=T)
    model.C_buy = Param(initialize=0.10)
    model.C_sell = Param(initialize=0.10)
    model.initial_SOC = Param(initialize=initial_SOC)
    model.SOC_max = Param(initialize=SOC_max)
    model.SOC_min = Param(initialize=SOC_min)
    model.P_load_min = Param(model.T, initialize=d_min_values, within = Reals)
    model.P_load_max = Param(model.T, initialize=d_max_values, within = Reals)
    model.P_ess_min = Param(initialize=-delta_charge_max)
    model.P_ess_max = Param(initialize=+delta_charge_max)
    model.eta = Param(initialize=eta)
    model.P_gen = Param(model.T, initialize=production_values)

    # Decision Variables
    def P_load_bounds(model, t):
        return (model.P_load_min[t], model.P_load_max[t])

    # Variables
    model.P_load = Var(model.T, within=NonNegativeReals, bounds=P_load_bounds)
    model.P_ess = Var(model.T, domain = Reals, bounds=(model.P_ess_min, model.P_ess_max)) # ess power flow variation in time frame (negative charge, positive discharge)
    model.P_grid = Var(model.T, domain=Reals) #Net exchanges with grid (positive buy, negative sell)
    model.SOC = Var(model.T, domain=NonNegativeReals, bounds = (model.SOC_min, model.SOC_max))
    model.P_grid_positive = Var(model.T, within=NonNegativeReals) #Purchases from grid
    model.P_grid_negative = Var(model.T, within=NonNegativeReals) #Energy sold to the grid
    model.is_positive = Var(model.T, within=Binary) #Binary variable to manage P_grid_positive and P_grid_negative

    # F.O. Optimize costs
    # maximize savings
    #def objective_rule(model):
    #    return sum(
    #        model.C_buy * model.P_grid_positive[t] - 
    #        model.C_sell * model.P_grid_negative[t] 
    #        for t in model.T
    #    )
    #model.objective = Objective(rule=objective_rule, sense=minimize)

    #F.O. Maximize self-consumption
    def objective_rule(model): 
        return sum(model.P_grid_positive[t] for t in T)
    model.objective = Objective(rule = objective_rule, sense = minimize)
    #Constraints

    #Energy balance: 
    def energy_balance(model, t): 
        return model.P_load[t] == model.P_gen[t] + model.P_ess[t] + model.P_grid[t]

    model.energy_balance = Constraint(model.T, rule=energy_balance)

    #SOC update
    def soc_update(model, t): 
        if t == 0: 
            return model.SOC[t] == model.initial_SOC - model.eta * model.P_ess[t]
        else: 
            return model.SOC[t] == model.SOC[t-1] - model.eta * model.P_ess[t]

    model.soc_update = Constraint(model.T, rule=soc_update)

    ################################################################################################
    """The following constraints are used to find P_grid_positive and P_grid_negative (to linearize the obj func.)"""

    # If P_grid[t] is positive, P_grid_positive[t] represents its magnitude, else it's forced to be 0.
    # The big-M method ensures this constraint is satisfied without making the problem non-linear.
    def positive_link_rule(model, t):
        return model.P_grid[t] <= model.P_grid_positive[t] + bigM * (1 - model.is_positive[t])
    model.positive_link = Constraint(model.T, rule=positive_link_rule)
    # If P_grid[t] is negative, P_grid_negative[t] represents its magnitude (as a positive value), else it's forced to be 0.
    # The big-M method ensures this constraint is satisfied without making the problem non-linear.
    def negative_link_rule(model, t):
        return model.P_grid[t] >= -model.P_grid_negative[t] - bigM * model.is_positive[t]
    model.negative_link = Constraint(model.T, rule=negative_link_rule)
    # These constraints ensure that P_grid_positive[t] and P_grid_negative[t] cannot both be non-zero at the same time, 
    # effectively implementing the if-then-else logic in a linear manner.
    def disjunction_rule(model, t):
        return model.P_grid_positive[t] <= bigM * model.is_positive[t]
    model.disjunction = Constraint(model.T, rule=disjunction_rule)
    def disjunction_rule2(model, t):
        return model.P_grid_negative[t] <= bigM * (1 - model.is_positive[t])
    model.disjunction2 = Constraint(model.T, rule=disjunction_rule2)

    # Solve the model
    solver = SolverFactory('glpk', executable = 'C:\glpk\w64\glpsol.exe') 
    #solver = SolverFactory('ipopt', executable='C:\\ipopt\\bin\\ipopt.exe')
    #TransformationFactory('gdp.bigm').apply_to(model)
    solver.solve(model)#, tee = True)

    ## Print the results
    #print("\n--- Optimization Results ---\n")
    #print(results_df)
    #model.display()
    #for t in model.T:
    #    print(f"At time {t}, Production: {model.P_gen[t]} P_load: {model.P_load[t]()}, P_ess: {model.P_ess[t]()}, SOC: {model.SOC[t]()}, P_grid: {model.P_grid[t]()}, is_positive: {model.is_positive[t]()})")


    # Initialize empty lists for each decision variable you want to save
    P_load_list = []
    P_ess_list = []
    P_grid_list = []
    SOC_list = []

    # Iterate over the time periods and append the value of the decision variable at each time period to the list
    for t in model.T:
        P_load_list.append(value(model.P_load[t])) 
        P_ess_list.append(value(model.P_ess[t])) #Discharge is positive
        P_grid_list.append(-value(model.P_grid[t])) #in the framework withdrawals are negative
        SOC_list.append(value(model.SOC[t]))

    P_ess_discharge = [item if item > 0 else 0 for item in P_ess_list]
    self_consumption = [min (P_load_list[t], model.P_gen[t] + P_ess_discharge[t])for t in range(len(P_load_list))]

    best_sol_parameters = {} # dictionary with best sol parameters
    best_sol_parameters['Load'] = P_load_list
    best_sol_parameters["grid_energy"] = P_grid_list
    best_sol_parameters["self_consumption"] = self_consumption
    best_sol_parameters["battery_energy"] = SOC_list
    return_df = pd.DataFrame(best_sol_parameters)
    return return_df