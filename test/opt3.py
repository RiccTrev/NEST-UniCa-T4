from pyomo.environ import *
import pandas as pd
# Assuming 24 time periods (e.g., hours)
T = range(5)

model = ConcreteModel()

#Sample Data
d_min_values = {0: 1, 1: 3, 2: 5, 3: 2, 4: 1}
d_max_values = {0: 5, 1: 5, 2: 6, 3: 5, 4: 5}
production_values ={0: 5, 1: 6, 2: 3, 3: 4, 4: 5}
maximum_storage_capacity = 10
eta = 0.9
Delta_t = 1
M = bigM = 1000000000000000000000000000000000000
#Parmeters
time_steps = range(5)  # 24 hours
model.T = Set(initialize=time_steps)
C_buy = 0.1
C_sell = 0.1
initial_soc = 0
model.C_buy = Param(initialize=0.10)  # Cost per unit of power purchased from the grid: $0.15/kWh
model.C_sell = Param(initialize=0.10) # Payment received per unit of power sold to the grid: $0.10/kWh
#model.M = Param(initialize=1000000000000000000000000000000000000)      # A large constant
model.initial_soc = Param(initialize=0)
model.SOC_max = Param(initialize=10)
model.SOC_min = Param(initialize=0)
model.P_load_min = Param(model.T, initialize=d_min_values)
model.P_load_max = Param(model.T, initialize=d_max_values)
model.P_ess_min = Param(initialize=-20)  # Max charging rate
model.P_ess_max = Param(initialize=+20)   # Max discharging rate
model.eta = Param(initialize=1)
model.P_gen = Param(model.T, initialize = production_values)


# Decision Variables
def P_load_bounds(model, t):
    return (model.P_load_min[t], model.P_load_max[t])

model.P_load = Var(model.T, within=NonNegativeReals, bounds=P_load_bounds)
model.P_ess = Var(model.T, bounds=(model.P_ess_min, model.P_ess_max))
model.P_grid = Var(model.T, domain=Reals)
model.SOC = Var(model.T, bounds=(model.SOC_min, model.SOC_max))
model.z = Var(model.T, within=Binary)
model.y = Var(model.T, within=NonNegativeReals)

def objective_rule(model):
    return sum(model.C_buy * model.y[t] for t in T) - sum(model.C_sell * (-model.P_grid[t]) * (1-model.z[t]) for t in T)

model.objective = Objective(rule=objective_rule, sense=minimize)

# Constraints

# Load demand and generation constraint
def load_gen_constraint_rule(model, t):
    return model.P_load[t] == model.P_gen[t] + model.P_ess[t] + model.P_grid[t]
model.load_gen_constraint = Constraint(T, rule=load_gen_constraint_rule)

# State of charge update constraint
#def SOC_update_rule(model, t):
#    if t == 0:
#        return model.SOC[t] == initial_soc - (model.P_ess[t] * Delta_t) * eta
#    return model.SOC[t] == model.SOC[t-1] - (model.P_ess[t] * Delta_t) * eta
#model.SOC_update_rule = Constraint(T, rule=SOC_update_rule)

def SOC_update_rule(model, t):
    if t == 0:
        return model.SOC[t] == initial_soc - (model.P_ess[t] * Delta_t) * eta
    else: 
        return model.SOC[t] == model.SOC[t-1] - (model.P_ess[t] * Delta_t) * eta
model.SOC_update_rule = Constraint(T, rule=SOC_update_rule)

# ESS not discharging when selling power to the grid
def ESS_discharge_rule(model, t):
    return model.P_ess[t] + M * model.z[t] <= M
model.ESS_discharge_constraint = Constraint(T, rule=ESS_discharge_rule)

# PGRID no take when charging not discharging when selling power to the grid
def grid_rule(model, t):
    return model.P_grid[t] + M * model.z[t] >= 0
model.grid_rule = Constraint(T, rule=grid_rule)

## Definitions for binary variable z
#def z_definition_rule1(model, t):
#    return model.P_grid[t] >= -model.M * (1-model.z[t])
#model.z_definition_constraint1 = Constraint(T, rule=z_definition_rule1)
#
#def z_definition_rule2(model, t):
#    return model.P_grid[t] <= model.M * model.z[t]
#model.z_definition_constraint2 = Constraint(T, rule=z_definition_rule2)
def linearization_constraint1(model, t):
    return model.y[t] >= 0

def linearization_constraint2(model, t):
    return model.y[t] >= model.P_grid[t] - bigM * (1 - model.z[t])

def linearization_constraint3(model, t):
    return model.y[t] <= model.P_grid[t]

def linearization_constraint4(model, t):
    return model.y[t] <= bigM * model.z[t]

model.linearization_constraint1 = Constraint(model.T, rule=linearization_constraint1)
model.linearization_constraint2 = Constraint(model.T, rule=linearization_constraint2)
model.linearization_constraint3 = Constraint(model.T, rule=linearization_constraint3)
model.linearization_constraint4 = Constraint(model.T, rule=linearization_constraint4)
# Solve the model
solver = SolverFactory('glpk', executable = 'C:\glpk\w64\glpsol.exe') 
#solver = SolverFactory('ipopt', executable = 'C:\\ipopt\\bin\\ipopt.exe')
#solver.options['max_iter'] = 10000  # large number to represent "unlimited" iterations
#solver.options['tol'] = 0.001  # a smaller tolerance might result in more iterations
solver.solve(model)


# Collect the results
result_data = {
    "Time Period": list(model.T),
    "Power Load": [value(model.P_load[t]) for t in model.T],
    "Power from/to ESS": [value(model.P_ess[t]) for t in model.T],
    "Power from/to Grid": [value(model.P_grid[t]) for t in model.T],
    "State of Charge": [value(model.SOC[t]) for t in model.T],
    "Binary variable z": [value(model.z[t]) for t in model.T],
    "Production Values": [value(model.P_gen[t]) for t in model.T]  # Added this line
}

# Create a DataFrame
results_df = pd.DataFrame(result_data)

# Optionally, transpose the DataFrame to have variables as rows and time periods as columns
results_df = results_df.set_index("Time Period").T

# Print the results
print("\n--- Optimization Results ---\n")
print(results_df)
