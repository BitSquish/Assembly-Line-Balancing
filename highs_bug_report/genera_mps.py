import highspy
from src.models import NaiveModel
from tests.helpers import random_instance

# 1. Genera e salva rnd37 (quello che dà "Infeasible" falso)
inst37 = random_instance(37, n=7, m=3, p=0.3)
prob37 = NaiveModel(inst37).build()
prob37.writeMPS("rnd37.mps")
print("Salvato rnd37.mps")

# 2. Genera e salva rnd30 (quello che dà "Solve error")
inst30 = random_instance(30, n=7, m=4, p=0.5)
prob30 = NaiveModel(inst30).build()
prob30.writeMPS("rnd30.mps")
print("Salvato rnd30.mps")

# 3. Verifica finale su rnd37 con presolve disattivato
print("\nVerifica HiGHS puro su rnd37.mps con presolve=off (Dovrebbe stampare kOptimal e 17.0):")
h = highspy.Highs()
h.setOptionValue("presolve", "off")
h.readModel("rnd37.mps")
h.run()
print(h.getModelStatus(), h.getInfo().objective_function_value)