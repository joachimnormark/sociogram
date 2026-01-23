import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
import math
from io import BytesIO
import os
from datetime import datetime
import numpy as np


# === Funktion til at læse CSV med flere mulige separatorer ===
def read_csv_smart(file, header):
    for sep in [";", ",", "\t"]:
        file.seek(0)
        try:
            return pd.read_csv(file, sep=sep, header=header)
        except Exception:
            continue
    raise ValueError("Kunne ikke læse CSV-filen. Prøv at gemme den igen som CSV i Excel.")


# === Layout-funktioner ===

def layout_circle(names):
    n = len(names)
    radius = 5
    positions = {}
    for i, name in enumerate(names):
        angle = 2 * math.pi * i / n
        positions[name] = (radius * math.cos(angle), radius * math.sin(angle))
    return positions


def layout_grid(names):
    n = len(names)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    positions = {}
    spacing = 3
    for idx, name in enumerate(names):
        r = idx // cols
        c = idx % cols
        positions[name] = (c * spacing, -r * spacing)
    return positions


def layout_force(names, edges, iterations=300, step=0.01):
    # Simpel force-layout (repulsion + attraction)
    n = len(names)
    pos = {name: np.random.randn(2) for name in names}

    for _ in range(iterations):
        forces = {name: np.zeros(2) for name in names}

        # Repulsion
        for a in names:
            for b in names:
                if a == b:
                    continue
                diff = pos[a] - pos[b]
                dist = np.linalg.norm(diff) + 0.01
                forces[a] += diff / dist**2

        # Attraction (edges)
        for a, b in edges:
            if a in pos and b in pos:
                diff = pos[b] - pos[a]
                dist = np.linalg.norm(diff) + 0.01
                forces[a] += diff * 0.01
                forces[b] -= diff * 0.01

        # Apply forces
        for name in names:
            pos[name] += forces[name] * step

    return pos


# === Streamlit UI ===

st.title("Sociogram-generator")

klasse_navn = st.text_input("Indtast klassens navn (fx 7.A):")

layout_valg = st.selectbox(
    "Vælg layout",
    ["Cirkel-layout", "Grid-layout", "Force-layout"]
)

uploaded_file = st.file_uploader("Vælg fil", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:

    # === 1. Find filtype ===
    ext = os.path.splitext(uploaded_file.name)[1].lower()

    # === 2. Læs rå data uden header ===
    if ext in [".xlsx", ".xls"]:
        df_raw = pd.read_excel(uploaded_file, header=None)
    else:
        df_raw = read_csv_smart(uploaded_file, header=None)

    # === 3. Tjek om første række er header ===
    first_cell = str(df_raw.iloc[0, 0]).strip().lower()

    if first_cell == "elev":
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(uploaded_file, header=0)
        else:
            df = read_csv_smart(uploaded_file, header=0)
        df.columns = df.columns.str.strip().str.lower()
    else:
        df = df_raw.copy()
        num_cols = df.shape[1]
        df.columns = ["elev"] + [str(i) for i in range(1, num_cols)]
        df.columns = df.columns.str.lower()

    # === 4. Find valgkolonner ===
    all_cols = list(df.columns)
    if "elev" not in all_cols:
        st.error("Kunne ikke finde en kolonne med elevnavne.")
        st.stop()

    choice_cols = [c for c in all_cols if c != "elev"]
    num_choices = len(choice_cols)

    if num_choices < 2 or num_choices > 4:
        st.error("Filen skal have 3, 4 eller 5 kolonner (elev + 2-4 valg).")
        st.stop()

    # === 5. Tjek for manglende valg ===
    missing = []
    for _, row in df.iterrows():
        elev = row["elev"]
        for c in choice_cols:
            if pd.isna(row[c]) or str(row[c]).strip() == "":
                missing.append(elev)
                break

    if missing:
        names = ", ".join(sorted(set(missing)))
        st.error(f"Følgende elever peger ikke på {num_choices} andre: {names}")
        st.stop()

    # === 6. Tjek for selv-reference ===
    self_ref = []
    for _, row in df.iterrows():
        elev_norm = str(row["elev"]).strip().lower()
        for c in choice_cols:
            if elev_norm == str(row[c]).strip().lower():
                self_ref.append(row["elev"])
                break

    if self_ref:
        names = ", ".join(sorted(set(self_ref)))
        st.error(f"Følgende elever peger på sig selv: {names}")
        st.stop()

    # === 7. Beregn kontakter ===
    all_names = pd.concat([df["elev"]] + [df[c] for c in choice_cols])
    contacts_count = all_names.value_counts().to_dict()

    # === 8. Layout ===
    names = list(contacts_count.keys())

    if layout_valg == "Cirkel-layout":
        positions = layout_circle(names)
    elif layout_valg == "Grid-layout":
        positions = layout_grid(names)
    else:
        edges_for_force = [(row["elev"], row[c]) for _, row in df.iterrows() for c in choice_cols]
        positions = layout_force(names, edges_for_force)

    # === 9. Edges ===
    edges = []
    for _, row in df.iterrows():
        elev = row["elev"]
        for c in choice_cols:
            edges.append((elev, row[c]))

    mutual = set()
    for a, b in edges:
        if (b, a) in edges:
            mutual.add((a, b))
            mutual.add((b, a))

    # === 10. Tegn sociogram ===
    fig, ax = plt.subplots(figsize=(10, 10))

    # Fast radius
    R = 0.35

    def farve(n):
        if n < 3:
            return "red"
        elif n < 6:
            return "orange"
        else:
            return "green"

    # Cirkler
    for elev in names:
        x, y = positions[elev]
        circle = Circle((x, y), R, color=farve(contacts_count[elev]), ec="black", zorder=2)
        ax.add_patch(circle)
        ax.text(x, y, elev, ha="center", va="center", fontsize=10, zorder=3)

    # Pile
    for start, end in edges:
        if start not in positions or end not in positions:
            continue

        x1, y1 = positions[start]
        x2, y2 = positions[end]

        dx, dy = x2 - x1, y2 - y1
        dist = math.sqrt(dx**2 + dy**2)
        if dist == 0:
            continue

        new_x1 = x1 + dx * (R / dist)
        new_y1 = y1 + dy * (R / dist)
        new_x2 = x2 - dx * (R / dist)
        new_y2 = y2 - dy * (R / dist)

        if (start, end) in mutual:
            color = "green"
            lw = 3
        else:
            color = "black"
            lw = 1

        arrow = FancyArrowPatch(
            (new_x1, new_y1),
            (new_x2, new_y2),
            arrowstyle="->",
            mutation_scale=15,
            color=color,
            linewidth=lw,
            zorder=3,
        )
        ax.add_patch(arrow)

    # === 11. Titel ===
    dato = datetime.now().strftime("%d-%m-%Y")

    titel = f"Sociogram for {klasse_navn}" if klasse_navn else "Sociogram"
    undertitel = f"Alle peger på {num_choices} andre"
    dato_tekst = f"Genereret den {dato}"

    plt.title(f"{titel}\n{undertitel}\n{dato_tekst}", fontsize=14)
    plt.axis("off")

    st.pyplot(fig)

    # === 12. PDF-download ===
    pdf_buffer = BytesIO()
    fig.savefig(pdf_buffer, format="pdf")
    pdf_buffer.seek(0)

    st.download_button(
        label="Download sociogram som PDF",
        data=pdf_buffer,
        file_name="sociogram.pdf",
        mime="application/pdf",
    )
