#print(Expr_if(IF=(t == 0), THEN=(model.SOC[t] == model.initial_SOC - model.eta * model.P_ess[t]), ELSE=(model.SOC[t] == model.SOC[t-1] - model.eta * model.P_ess[t])))#
    #return Expr_if(IF=(t == 0), THEN=(model.SOC[t] == model.initial_SOC - model.eta * model.P_ess[t]), ELSE=(model.SOC[t] == model.SOC[t-1] - model.eta * model.P_ess[t]))   


#model.objective = Objective(sum(model.C_buy * max(0, model.P_grid[t]) - model.C_sell * max(0, -model.P_grid[t]) for t in model.T), sense=minimize)