FULL_EXTRACTION: str = """\
You are an expert at reading industrial control panel screenshots with 100% accuracy.
This is an ELECTRON PROCESSING SYSTEM (AQUILLA / VIVIRAD) panel.

Extract ALL numeric values from these sections:

1. PUISSANCE ICT table (3 rows: B-C, C-A, A-B):
   - Tension primaire (V)
   - Courant primaire (A) with zone letter (A/B/C) and value
   - Courant secondaire (A) with zone letter (A/B/C) and value

2. ACCELERATEURS table (2 rows: zone A, zone B):
   - R Icol (KV)
   - Courant colonne (uA)
   - Vide (Torr) in scientific notation like "4.8e-007"
   - Courant aperture (uA)

3. Global values:
   - Tension KV (large colored box)
   - Charge mA (large colored box)
   - Faisceau mA zone A and zone B (colored boxes)

RULES:
- Read EXACTLY what is on screen - never guess
- Use "." as decimal separator
- Vide must be scientific notation string like "4.8e-007"
- If unreadable write "UNREADABLE"

Return ONLY this JSON (no markdown, no explanation):
{
  "puissance_ict": [
    {"zone_tension":"B-C","tension_primaire_v":0,"zone_courant_primaire":"A","courant_primaire_a":0,"zone_courant_secondaire":"A","courant_secondaire_a":0},
    {"zone_tension":"C-A","tension_primaire_v":0,"zone_courant_primaire":"B","courant_primaire_a":0,"zone_courant_secondaire":"B","courant_secondaire_a":0},
    {"zone_tension":"A-B","tension_primaire_v":0,"zone_courant_primaire":"C","courant_primaire_a":0,"zone_courant_secondaire":"C","courant_secondaire_a":0}
  ],
  "accelerateurs_zones": [
    {"zone":"A","r_icol_kv":0,"courant_colonne_ua":0,"vide_torr":"0","courant_aperture_ua":0},
    {"zone":"B","r_icol_kv":0,"courant_colonne_ua":0,"vide_torr":"0","courant_aperture_ua":0}
  ],
  "accelerateurs_global": {
    "tension_kv":0,"charge_ma":0,"faisceau_ma_a":0,"faisceau_ma_b":0
  }
}
"""

PUISSANCE_ICT: str = """\
This is a CROPPED view of a Puissance ICT table. Read EVERY value exactly.
3 rows (B-C, C-A, A-B). Columns: Tension primaire (V), Courant primaire (A) with zone letter, Courant secondaire (A) with zone letter.
Use "." as decimal. Return ONLY JSON:
{"puissance_ict":[
  {"zone_tension":"B-C","tension_primaire_v":0,"zone_courant_primaire":"A","courant_primaire_a":0,"zone_courant_secondaire":"A","courant_secondaire_a":0},
  {"zone_tension":"C-A","tension_primaire_v":0,"zone_courant_primaire":"B","courant_primaire_a":0,"zone_courant_secondaire":"B","courant_secondaire_a":0},
  {"zone_tension":"A-B","tension_primaire_v":0,"zone_courant_primaire":"C","courant_primaire_a":0,"zone_courant_secondaire":"C","courant_secondaire_a":0}
]}
"""

ACCELERATEURS: str = """\
This is a CROPPED view of an Accelerateurs table. Read EVERY value exactly.
2 rows (zone A, zone B). Columns: R Icol (KV), Courant colonne (uA), Vide (Torr) in scientific notation, Courant aperture (uA).
Use "." as decimal. Vide as string. Return ONLY JSON:
{"accelerateurs_zones":[
  {"zone":"A","r_icol_kv":0,"courant_colonne_ua":0,"vide_torr":"0","courant_aperture_ua":0},
  {"zone":"B","r_icol_kv":0,"courant_colonne_ua":0,"vide_torr":"0","courant_aperture_ua":0}
]}
"""

GLOBAL_VALUES: str = """\
This is a CROPPED view showing global values from an electron processing panel.
Read exactly: Tension KV, Charge mA, Faisceau mA zone A, Faisceau mA zone B.
Use "." as decimal. Return ONLY JSON:
{"accelerateurs_global":{"tension_kv":0,"charge_ma":0,"faisceau_ma_a":0,"faisceau_ma_b":0}}
"""
