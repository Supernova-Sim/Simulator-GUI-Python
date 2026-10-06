from hefesto.modelos import build_rocket

f = build_rocket()
print("rail_buttons:", type(f.rail_buttons))
print("nosecone:    ", type(f.nosecone))
print("fins:        ", type(f.fins))
print("motor:       ", type(f.motor))
print("unreefed:    ", type(f.unreefed))
print("reefed:      ", type(f.reefed))
f_free = build_rocket(tipo_aletas="freeform")
f_trap = build_rocket(tipo_aletas="trapezio")

print("freeform fins:  ", type(f_free.fins))
print("trapezio fins:  ", type(f_trap.fins))