from pyomo.environ import *
# Sample data
time_periods = [0, 1, 2, 3, 4]
#d_min_values = {0: 1, 1: 1, 2: 1, 3: 2, 4: 3}
#d_max_values = {0: 2, 1: 2, 2: 4, 3: 6, 4: 7}
d_min_values = {0: 1, 1: 1, 2: 1, 3: 1, 4: 1}
d_max_values = {0: 5, 1: 5, 2: 5, 3: 5, 4: 5}
production_values = {0: 5, 1: 6, 2: 3, 3: 4, 4: 5}
maximum_storage_capacity = 10
charging_efficiency = 0.9
discharging_efficiency = 0.8
lambda_value = 0.1

# Create a model
model = ConcreteModel()

# Define sets
model.T = Set(initialize=time_periods)

# Parameters
model.D_min = Param(model.T, initialize=d_min_values)
model.D_max = Param(model.T, initialize=d_max_values)
model.P = Param(model.T, initialize=production_values)
model.S_max = Param(initialize=maximum_storage_capacity)
model.eta_ch = Param(initialize=charging_efficiency)
model.eta_dch = Param(initialize=discharging_efficiency)
model.lambda_ = Param(initialize=lambda_value)

# Variables
model.D = Var(model.T, domain=NonNegativeReals)  # Demand
model.S = Var(model.T, domain=NonNegativeReals, bounds=(0, model.S_max))  # Storage level
model.G = Var(model.T, domain=Reals)  # Grid interaction
model.N = Var(model.T, domain=Reals)  # Net storage change
model.is_charging = Var(model.T, within=Binary)  # Charging state

# Constraints
def demand_bounds_rule(model, t):
    return (model.D_min[t], model.D[t], model.D_max[t])

model.demand_bounds = Constraint(model.T, rule=demand_bounds_rule)

def storage_dynamics_rule(model, t):
    if t == 0:
        return model.S[t] == 0
    else:
        return model.S[t] == (model.S[t-1] + model.N[t] * model.eta_ch * model.is_charging[t]
                              - model.N[t] * model.eta_dch * (1 - model.is_charging[t]))

model.storage_dynamics = Constraint(model.T, rule=storage_dynamics_rule)

model.charge_or_discharge = Constraint(model.T, rule=lambda model, t: model.N[t] * (2*model.is_charging[t]-1) >= 0)

def energy_balance_rule(model, t):
    return model.P[t] + model.G[t] - model.N[t] == model.D[t]

model.energy_balance = Constraint(model.T, rule=energy_balance_rule)

# Objective
def objective_rule(model):
    return sum(model.P[t] for t in model.T) - model.lambda_ * sum(abs(model.G[t]) for t in model.T)

model.objective = Objective(rule=objective_rule, sense=maximize)


# Create a solver and solve
#solver = SolverFactory('ipopt', executable = 'C:\\ipopt\\bin\\ipopt.exe')
solver = SolverFactory('glpk', executable = 'C:\glpk\w64\glpsol.exe') 
TransformationFactory('gdp.bigm').apply_to(model)
# Set options
#solver.options['max_iter'] = 1000000  # large number to represent "unlimited" iterations
#solver.options['tol'] = 0.00001  # a smaller tolerance might result in more iterations
#solver.executable =   # Specify the correct path to your glpsol executable
results = solver.solve(model, tee=True)


# Check if the solution is optimal and then display results
if results.solver:#.status == 'ok':#and results.solver.termination_condition == 'optimal':
    # display the results
    model.display()

    # Structured result output
    print("\nDecision Variable Outputs:")
    for t in model.T:
        print(f"Period {t}:")
        print(f"  Demand (D): {value(model.D[t])}")
        print(f"  Storage (S): {value(model.S[t])}")
        print(f"  Grid Interaction (G): {value(model.G[t])}")
        print(f"  Net Storage Change (N): {value(model.N[t])}")
else:
    print("No optimal solution found.")
