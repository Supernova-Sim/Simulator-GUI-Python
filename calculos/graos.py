import math

graos = [
    # Grãos 1 a 4 (BATES 1-4)
    {"id": 1, "massa": 1.748, "length": 0.15, "core": 0.041, "web": 0.029},
    {"id": 2, "massa": 1.748, "length": 0.15, "core": 0.041, "web": 0.029},
    {"id": 3, "massa": 1.748, "length": 0.15, "core": 0.041, "web": 0.029},
    {"id": 4, "massa": 1.748, "length": 0.15, "core": 0.041, "web": 0.029},
    # Grãos 5 e 6 (BATES 5-6)
    {"id": 5, "massa": 1.480, "length": 0.15, "core": 0.054, "web": 0.022},
    {"id": 6, "massa": 1.480, "length": 0.15, "core": 0.054, "web": 0.022}
]



def calcular_raio(core, web):
    """Calcula o raio interno e externo em metros."""
    raio_interno = core / 2
    diametro_externo = core + (2 * web)
    raio_externo = diametro_externo / 2
    return raio_interno, raio_externo


def calcular_volume(raio_interno, raio_externo, length):
    """Calcula o volume do cilindro oco em m³."""
    area_seccao = math.pi * (raio_externo ** 2 - raio_interno ** 2)
    volume = area_seccao * length
    return volume


massa_total = 0.0
volume_total = 0.0
momento_total = 0.0  # Usado para calcular o centro de massa
posicao_atual = 0.0  # Posição Z inicial (base do primeiro grão)

soma_raios_internos = 0.0
soma_raios_externos = 0.0
num_graos = len(graos)

print("=" * 60)
print("CÁLCULO DE PROPRIEDADES DOS GRÃOS")
print("=" * 60)

for grao in graos:

    m = grao["massa"]
    L = grao["length"]
    core = grao["core"]
    web = grao["web"]

    # 1. Cálculos de Raio
    r_in, r_out = calcular_raio(core, web)

    soma_raios_internos += r_in
    soma_raios_externos += r_out

    # 2. Cálculo de Volume e Densidade
    vol = calcular_volume(r_in, r_out, L)
    densidade = m / vol

    # 3. Cálculo do Centro de Massa individual
    # O centro geométrico do grão está na metade do seu comprimento
    cg_grao = posicao_atual + (L / 2)

    # Acumulando totais
    massa_total += m
    volume_total += vol
    momento_total += m * cg_grao

    # Exibindo resultados do grão
    print(f"Grão {grao['id']}:")
    print(f"  Raio Interno: {r_in:.4f} m | Raio Externo: {r_out:.4f} m")
    print(f"  Volume: {vol:.6f} m³ | Densidade: {densidade:.1f} kg/m³")
    print(f"  Posição do CG individual: {cg_grao:.4f} m")
    print("-" * 60)

    # Atualiza a posição para o próximo grão (empilhamento)
    posicao_atual += L

#resultados

raio_interno_medio = soma_raios_internos / num_graos
raio_externo_medio = soma_raios_externos / num_graos

densidade_media = massa_total / volume_total
cg_total = momento_total / massa_total

print("\n" + "=" * 60)
print("RESULTADOS FINAIS DO CONJUNTO (STACK)")
print("=" * 60)
print(f"Massa Total: {massa_total:.3f} kg")
print(f"Volume Total: {volume_total:.6f} m³")
print(f"Densidade Média: {densidade_media:.1f} kg/m³")
print(f"Comprimento Total: {posicao_atual:.3f} m")
print(f"Coordenada do Centro de Massa (CG): {cg_total:.4f} m")
print("MÉDIAS GEOMÉTRICAS DOS GRÃOS:")
print(f"  Raio Interno Médio: {raio_interno_medio:.5f} m")
print(f"  Raio Externo Médio: {raio_externo_medio:.5f} m")
print("=" * 60)

# Dica sobre o sistema de coordenadas
print("\nNOTA: O CG foi calculado assumindo que a base do primeiro grão")
print("está na coordenada Z = 0. Se o seu software usar a garganta do")
print("bocal como zero, some a distância do bocal até a base do grão 1.")