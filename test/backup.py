from pyomo.environ import *

# Assuming data is given as lists/arrays:
P_GEN = {1: 6, 2: 3, 3: 4, 4: 5, 5: 10}
P_LOAD_MIN = {1: 3, 2: 5, 3: 2, 4: 1, 5:1}
P_LOAD_MAX =  {1: 5, 2: 6, 3: 5, 4: 5, 5: 4}
C_sell =0.01
C_buy = 0.1
SOC_initial = 4
gamma_trip = 1
delta_t = 1
min_cap = 0
max_cap = 5
delta_charge_max = 10

T = len(P_GEN)
M = 10e6  # A sufficiently large number

model = ConcreteModel()

# Set of time periods
model.T = Set(initialize=range(1, T+1))  # Assuming you have the value of T

# Given parameters
model.P_GEN = Param(model.T, initialize=P_GEN , within=NonNegativeReals)  # Initialize with a suitable mapping for P_GEN(t)
model.P_LOAD_MIN = Param(model.T, initialize=P_LOAD_MIN, within=Reals)  # Initialize with a suitable mapping for P_LOAD_MIN(t)
model.P_LOAD_MAX = Param(model.T, initialize=P_LOAD_MAX, within=Reals)  # Initialize with a suitable mapping for P_LOAD_MAX(t)
model.C_sell = Param(initialize=C_sell, within=NonNegativeReals)
model.C_buy = Param(initialize=C_buy, within=NonNegativeReals)
model.SOC_initial = Param(initialize=SOC_initial, within=NonNegativeReals)
#model.P_GRID_sell = Var(model.T, domain=NonNegativeReals)
#model.P_GRID_buy = Var(model.T, domain=NonNegativeReals)

# Variables
model.P_LOAD = Var(model.T, domain=Reals)
model.P_ESS = Var(model.T, domain=Reals, bounds = (-delta_charge_max,delta_charge_max))
model.SOC = Var(model.T, domain=NonNegativeReals, bounds = (min_cap, max_cap), initialize = SOC_initial)
model.P_GRID = Var(model.T, domain=Reals)
model.delta = Var(model.T, domain=Binary)

def objective_rule(model):
    #return sum(
    #    -model.C_sell * max(0, model.P_GRID[t]) + model.C_buy * max(0, model.P_GRID[t]) 
    #    for t in model.T
    #)
    return sum(model.C_buy * model.P_GRID[t] * model.delta[t] - model.C_sell * (-model.P_GRID[t]) * (1 - model.delta[t]) for t in model.T)

# Constraints
def power_balance_rule(model, t):
    return model.P_LOAD[t] == model.P_GEN[t] + model.P_ESS[t] + model.P_GRID[t]

model.power_balance_constraint = Constraint(model.T, rule=power_balance_rule)

def load_power_limits_rule(model, t):
    return inequality(model.P_LOAD_MIN[t], model.P_LOAD[t], model.P_LOAD_MAX[t])

model.load_power_limits_constraint = Constraint(model.T, rule=load_power_limits_rule)

def soc_dynamics_rule(model, t):
    if t == 1:
        return model.SOC[t] == model.SOC_initial + gamma_trip * model.P_ESS[t] * delta_t  # Assuming gamma_trip and delta_t are given
    return model.SOC[t] == model.SOC[t-1] + gamma_trip * model.P_ESS[t] * delta_t

model.soc_dynamics_constraint = Constraint(model.T, rule=soc_dynamics_rule)

M = 1000  # Big M value; you might need to adjust based on your specific problem data

def battery_charge_restriction_rule(model, t):
    return model.P_ESS[t] <= M * (1 - model.delta[t])

model.battery_charge_restriction1 = Constraint(model.T, rule=battery_charge_restriction_rule)

def grid_power_rule(model, t):
    return model.P_GRID[t] <= M * model.delta[t]

model.grid_power_restriction = Constraint(model.T, rule=grid_power_rule)


# Solving the model
solver = SolverFactory('glpk', executable = 'C:\glpk\w64\glpsol.exe') 
#solver = SolverFactory('ipopt', executable = 'C:\\ipopt\\bin\\ipopt.exe')
#TransformationFactory('gdp.bigm').apply_to(model)
solver.solve(model)
#model.display()

# Print the results (you can also save them or use them further in your program)
for t in model.T:
    print(f"At time {t}, P_LOAD: {model.P_LOAD[t]()}, P_ESS: {model.P_ESS[t]()}, SOC: {model.SOC[t]()}, P_GRID: {model.P_GRID[t]()}, delta: {model.delta[t]()})")
    #print(f"At time {t}, P_LOAD: {model.P_LOAD[t]()}, P_ESS: {model.P_ESS[t]()}, SOC: {model.SOC[t]()}), P_GRID_sell: {model.P_GRID_sell[t]()}, P_GRID_buy: {model.P_GRID_buy[t]()}")

