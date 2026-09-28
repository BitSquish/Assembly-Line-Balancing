import highspy

for name in ("rnd37", "rnd30"):
    print(f"\n--- {name} ---")
    
    # 1. Run con presolve ON (genera il log)
    h = highspy.Highs()
    h.setOptionValue("log_file", f"{name}.log")
    h.readModel(f"{name}.mps")
    h.run()
    print(f"Status (presolve ON): {h.getModelStatus()}")
    
    # 2. Run con presolve OFF (verifica)
    h2 = highspy.Highs()
    h2.setOptionValue("presolve", "off")
    h2.readModel(f"{name}.mps")
    h2.run()
    print(f"Status (presolve OFF): {h2.getModelStatus()} - Obiettivo: {h2.getInfo().objective_function_value}")