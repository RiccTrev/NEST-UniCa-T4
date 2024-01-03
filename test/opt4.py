from pyomo.environ import *

# Sample data
num_time_periods = 5
T = range(num_time_periods)

# Parameters
ESS_max = 100
SOC_min = 0
SOC_initial = 0
eta = 0.9
Delta_t = 1  # Time step duration

PV = [10, 20, 30, 25, 15]  # PV production
L_min = [5, 10, 15, 10, 5]  # Minimum load
L_max = [25, 30, 35, 30, 25]  # Maximum load
C_grid = 0.12  # Cost of withdrawing
C_inj = 0.05  # Remuneration of injection

# Model
model = ConcreteModel()

# Sets
model.T = Set(initialize=T)

# Variables
model.SOC = Var(model.T, bounds=(SOC_min, ESS_max))  # State of Charge
model.L = Var(model.T, bounds=(min(L_min), max(L_max)))  # Load
model.P_grid = Var(model.T, within=NonNegativeReals)  # Power from grid
model.P_inj = Var(model.T, within=NonNegativeReals)  # Power to grid

# Objective
def objective_rule(model):
    return sum(C_grid * model.P_grid[t] - C_inj * model.P_inj[t] for t in model.T)
model.cost = Objective(rule=objective_rule, sense=minimize)

# Constraints

# Initial State of Charge
#def initial_soc_rule(model):
#    return model.SOC[0] == SOC_initial
#model.initial_soc = Constraint(rule=initial_soc_rule)

# ESS Dynamics
def ess_rule(model, t):
    if t == 0:
        return model.SOC[0] == SOC_initial  # Skip the first time period (t=0), because it's for initial SOC
    if t > 0:
        return model.SOC[t] == model.SOC[t-1] + eta * (PV[t] - model.L[t]) * Delta_t
model.ess = Constraint(model.T, rule=ess_rule)

# Load Dynamics
def load_rule(model, t):
    return (L_min[t], model.L[t], L_max[t])
model.load_dynamics = Constraint(model.T, rule=load_rule)

# Power Balance
def power_balance_rule(model, t):
    if t == 0:
        return model.L[t] == PV[t] + model.P_grid[t] - model.P_inj[t]  # SOC change not considered at t=0
    if t > 0:
        return model.L[t] == PV[t] + (model.SOC[t-1] - model.SOC[t]) / (eta * Delta_t) + model.P_grid[t] - model.P_inj[t]
model.power_balance = Constraint(model.T, rule=power_balance_rule)

# Solve
solver = SolverFactory('glpk', executable = 'C:\glpk\w64\glpsol.exe') 
results = solver.solve(model, tee=True)

# display the results
#model.display()
print("\nResults:")
for t in model.T:
    print(f"Time {t}: SOC={model.SOC[t]():.2f}, Load={model.L[t]():.2f}, P_grid={model.P_grid[t]():.2f}, P_inj={model.P_inj[t]():.2f}")
