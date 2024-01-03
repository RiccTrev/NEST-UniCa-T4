from pyomo.environ import *
import pandas as pd

# Assuming 5 time periods
T = range(5)

model = ConcreteModel()

# Sample Data
d_min_values = {0: 1, 1: 3, 2: 5, 3: 2, 4: 1}
d_max_values = {0: 5, 1: 5, 2: 6, 3: 5, 4: 5}
production_values = {0: 5, 1: 6, 2: 3, 3: 4, 4: 5}
maximum_storage_capacity = 10
eta = 0.9
Delta_t = 1

# Parameters
model.T = Set(initialize=T)
model.C_buy = Param(initialize=0.10)
model.C_sell = Param(initialize=0.10)
model.M = Param(initialize=10e100)
model.initial_soc = Param(initialize=0)
model.SOC_max = Param(initialize=10)
model.SOC_min = Param(initialize=0)
model.P_load_min = Param(model.T, initialize=d_min_values)
model.P_load_max = Param(model.T, initialize=d_max_values)
model.P_ess_min = Param(initialize=-20)
model.P_ess_max = Param(initialize=+20)
model.eta = Param(initialize=eta)
model.P_gen = Param(model.T, initialize=production_values)
model.capacita_da_installare_BESS = Param(initialize=maximum_storage_capacity)

# Decision Variables
def P_load_bounds(model, t):
    return (model.P_load_min[t], model.P_load_max[t])
# Variables
model.P_load = Var(model.T, within=NonNegativeReals, bounds=P_load_bounds)
model.P_ess = Var(model.T, bounds=(model.P_ess_min, model.P_ess_max))
model.P_grid = Var(model.T, domain=Reals)
model.SOC = Var(model.T, bounds=(model.SOC_min, model.SOC_max))
model.z = Var(model.T, within=Binary)

# Objective Function
model.objective = Objective(expr=sum(model.C_buy * model.P_grid[t] * model.z[t] - model.C_sell * (-model.P_grid[t]) * (1 - model.z[t]) for t in model.T), sense=minimize)

# Constraints
def energy_available_expr(model, t):
    return model.P_gen[t] + (model.SOC[t-1] if t != 0 else model.initial_soc)
model.energy_available = Expression(model.T, rule=energy_available_expr)

def load_gen_constraint_rule(model, t):
    return model.P_load[t] == model.P_gen[t] + model.P_ess[t] + model.P_grid[t]
model.load_gen_constraint = Constraint(model.T, rule=load_gen_constraint_rule)

def SOC_update_rule(model, t):
    if t == 0:
        return model.SOC[t] == model.initial_soc - (model.P_ess[t] * Delta_t) * eta
    if model.energy_available[t] >= model.P_load[t]:
        return model.SOC[t] == model.SOC[t-1] + (model.P_gen[t] - model.P_load[t]) * Delta_t * eta
    else:
        return model.SOC[t] == 0
model.SOC_update_rule = Constraint(model.T, rule=SOC_update_rule)

def grid_energy_calc_rule(model, t):
    if t == 0:
        return Constraint.Skip
    return model.P_grid[t] == (model.P_gen[t] - model.P_load[t] + model.P_ess[t]) * Delta_t * eta
model.grid_energy_calc = Constraint(model.T, rule=grid_energy_calc_rule)

def ESS_discharge_rule(model, t):
    return model.P_ess[t] + model.M * model.z[t] <= model.M
model.ESS_discharge_constraint = Constraint(model.T, rule=ESS_discharge_rule)

def z_definition_rule1(model, t):
    return model.P_grid[t] >= -model.M * (1-model.z[t])
model.z_definition_constraint1 = Constraint(model.T, rule=z_definition_rule1)

def z_definition_rule2(model, t):
    return model.P_grid[t] <= model.M * model.z[t]
model.z_definition_constraint2 = Constraint(model.T, rule=z_definition_rule2)

# Solve the model
solver = SolverFactory('ipopt', executable='C:\\ipopt\\bin\\ipopt.exe')
TransformationFactory('gdp.bigm').apply_to(model)

solver.solve(model)

# Collect the results
result_data = {
    "Time Period": list(model.T),
    "Power Load": [value(model.P_load[t]) for t in model.T],
    "Power from/to ESS": [value(model.P_ess[t]) for t in model.T],
    "Power from/to Grid": [value(model.P_grid[t]) for t in model.T],
    "State of Charge": [value(model.SOC[t]) for t in model.T],
    "Binary variable z": [value(model.z[t]) for t in model.T],
    "Production Values": [value(model.P_gen[t]) for t in model.T]
}

# Create a DataFrame
results_df = pd.DataFrame(result_data)
results_df = results_df.set_index("Time Period").T

# Print the results
print("\n--- Optimization Results ---\n")
print(results_df)
