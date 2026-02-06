import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
import math
from io import BytesIO
import os
from datetime import datetime
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def read_csv_smart(file, header):
    for sep in [";", ",", "\t"]:
        file.seek(0)
        try:
            return pd.read_csv(file, sep=sep, header=header)
        except Exception:
            continue
    raise ValueError("Kunne ikke læse CSV-filen.")


import numpy as np

def ellipse_edge_point(x0, y0, x1, y1, x2, y2, width, height):
    """
    Returnerer punktet hvor linjen fra (x1,y1) til (x2,y2)
    rammer ellipsen centreret i (x0,y0) med given width/height.
    """
    # Flyt koordinater så ellipsens center er (0,0)
    dx = x2 - x1
    dy = y2 - y1

    # Parametrisk linje: (x1 + t*dx, y1 + t*dy)
    # Ellipse ligning: (x/a)^2 + (y/b)^2 = 1
    a = width / 2
    b = height / 2

    # Flyt startpunktet til ellipsecenter
    X1 = x1 - x0
    Y1 = y1 - y0

    # Løs andengradsligning for t
    A = (dx*dx)/(a*a) + (dy*dy)/(b*b)
    B = 2*((X1*dx)/(a*a) + (Y1*dy)/(b*b))
    C = (X1*X1)/(a*a) + (Y1*Y1)/(b*b) - 1

    # Vi skal bruge den mindste positive t
    disc = B*B - 4*A*C
    t = (-B + np.sqrt(disc)) / (2*A)

    # Punktet på ellipsen
    ex = x1 + t*dx
    ey = y1 + t*dy
    return ex, ey


# === Layouts ===

def layout_circle(names):
    n = len(names)
    radius = 7
    positions = {}
    for i, name in enumerate(names):
        angle = 2 * math.pi * i / n
        positions[name] = (radius * math.cos(angle), radius * math.sin(angle))
    return positions


def layout_grid(names):
    n = len(names)
    cols = math.ceil(math.sqrt(n))
    spacing = 3
    positions = {}
    for idx, name in enumerate(names):
        r = idx // cols
        c = idx % cols
        positions[name] = (c * spacing, -r * spacing)
    return positions


# === Streamlit UI ===

st.title("Sociogram-generator")

klasse_navn = st.text_input("Indtast klassens navn (fx 7.A):")

layout_valg = st.selectbox("Vælg layout", ["Cirkel-layout", "Grid-layout"])

uploaded_file = st.file_uploader("Vælg fil", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:

    ext = os.path.splitext(uploaded_file.name)[1].lower()

    if ext in [".xlsx", ".xls"]:
        df_raw = pd.read_excel(uploaded_file, header=None)
    else:
        df_raw = read_csv_smart(uploaded_file, header=None)

    first_cell = str(df_raw.iloc[0, 0]).strip().lower()

    if first_cell == "elev":
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(uploaded_file, header=0)
        else:
            df = read_csv_smart(uploaded_file, header=0)
        df.columns = df.columns.str.strip().str.lower()
    else:
        df = df_raw.copy()
        df.columns = ["elev"] + [str(i) for i in range(1, df.shape[1])]
        df.columns = df.columns.str.lower()

    all_cols = list(df.columns)
    if "elev" not in all_cols:
        st.error("Kunne ikke finde en kolonne med elevnavne.")
        st.stop()

    choice_cols = [c for c in all_cols if c != "elev"]
    num_choices = len(choice_cols)

    if num_choices < 2 or num_choices > 4:
        st.error("Filen skal have 3, 4 eller 5 kolonner.")
        st.stop()

    # Manglende valg
    missing = []
    for _, row in df.iterrows():
        for c in choice_cols:
            if pd.isna(row[c]) or str(row[c]).strip() == "":
                missing.append(row["elev"])
                break

    if missing:
        st.error("Følgende elever mangler valg: " + ", ".join(sorted(set(missing))))
        st.stop()

    # Selvvalg
    self_ref = []
    for _, row in df.iterrows():
        elev = str(row["elev"]).strip().lower()
        for c in choice_cols:
            if elev == str(row[c]).strip().lower():
                self_ref.append(row["elev"])
                break

    if self_ref:
        st.error("Følgende elever peger på sig selv: " + ", ".join(sorted(set(self_ref))))
        st.stop()

    # Kontakter
    all_names = pd.concat([df["elev"]] + [df[c] for c in choice_cols])
    contacts_count = all_names.value_counts().to_dict()
    names = list(contacts_count.keys())

    # Layout
    if layout_valg == "Cirkel-layout":
        positions = layout_circle(names)
    else:
        positions = layout_grid(names)

    # Edges
    edges = []
    for _, row in df.iterrows():
        for c in choice_cols:
            edges.append((row["elev"], row[c]))

    mutual = set()
    for a, b in edges:
        if (b, a) in edges:
            mutual.add((a, b))
            mutual.add((b, a))

    # === Tegn figur ===
    fig, ax = plt.subplots(figsize=(10, 10))

    R = 0.35

    def farve(n):
    # n = antal gange navnet optræder i alle valg + egen række
    # Hvis n == 1 → ingen har valgt personen
        if n <= 1:
            return "black"
        elif n < 3:
            return "red"
        elif n < 6:
            return "orange"
        else:
            return "green"


            # === Cirkler (ovale noder) ===
    from matplotlib.patches import Ellipse

    for elev in names:
        x, y = positions[elev]

        ax.add_patch(
            Ellipse(
                (x, y),
                width=R * 4.2,      # bredere
                height=R * 3.2,     # lidt højere
                fill=False,
                edgecolor=farve(contacts_count[elev]),
                linewidth=2
            )
        )

        ax.text(
            x,
            y,
            elev,
            ha="center",
            va="center",
            fontsize=15
        )



       #DOBBELT? ax.text(x, y, elev, ha="center", va="center", fontsize=10)

    # === Pile ===
    for start, end in edges:
        x1, y1 = positions[start]
        x2, y2 = positions[end]

        dx, dy = x2 - x1, y2 - y1
        dist = math.sqrt(dx**2 + dy**2)
        if dist == 0:
            continue

     #   sx = x1 + dx * (R / dist)
      #  sy = y1 + dy * (R / dist)
     #   ex = x2 - dx * (R / dist)
      #  ey = y2 - dy * (R / dist)

        # Beregn ellipse-dimensioner for noderne
        node_width = R * 2.2
        node_height = R * 1.2

# Startpunkt: fra start-node mod end-node
        sx, sy = ellipse_edge_point(
            x1, y1, x1, y1, x2, y2,
            node_width, node_height
        )

# Slutpunkt: fra end-node mod start-node
        ex, ey = ellipse_edge_point(
            x2, y2, x2, y2, x1, y1,
            node_width, node_height
        )


        color = "green" if (start, end) in mutual else "black"
        lw = 3 if (start, end) in mutual else 1

        ax.add_patch(
            FancyArrowPatch(
                (sx, sy),
                (ex, ey),
                arrowstyle="->",
                mutation_scale=15,
                color=color,
                linewidth=lw
            )
        )

    # === Faste xlim/ylim ===
    if layout_valg == "Cirkel-layout":
        ax.set_xlim(-8, 8)
        ax.set_ylim(-8, 8)
    else:
        xs = [positions[n][0] for n in names]
        ys = [positions[n][1] for n in names]
        ax.set_xlim(min(xs) - 2, max(xs) + 2)
        ax.set_ylim(min(ys) - 2, max(ys) + 2)

    ax.set_aspect("equal")
    plt.axis("off")

           # === Farveforklaring (vandret under sociogrammet) ===
    legend_items = [
        ("Ingen peger på", "black"),
        ("Få valg (1-2)", "red"),
        ("Nogle valg (3-5)", "orange"),
        ("Mange valg (6+)", "green"),
    ]

    # Startposition i aksens koordinater
    base_x = 0.10      # venstre start
    base_y = -0.08     # under grafen
    spacing_x = 0.25   # vandret afstand mellem elementer
    circle_r = 0.015   # lille cirkel

    for i, (label, color) in enumerate(legend_items):
        x = base_x + i * spacing_x
        y = base_y

        # Lille hul cirkel
        ax.add_patch(
            Circle(
                (x, y),
                circle_r,
                fill=False,
                edgecolor=color,
                linewidth=2.5,
                transform=ax.transAxes,
                zorder=999,
                clip_on=False
            )
        )

        # Tekst
        ax.text(
            x + 0.03,
            y,
            label,
            va="center",
            fontsize=10,
            transform=ax.transAxes,
            zorder=999,
            clip_on=False
        )





    # Titel
    dato = datetime.now().strftime("%d-%m-%Y")
    titel = f"Sociogram for {klasse_navn}" if klasse_navn else "Sociogram"
    plt.title(f"{titel}\nAlle peger på {num_choices} andre\nGenereret den {dato}", fontsize=14)

    # PNG
    png_buffer = BytesIO()
    fig.savefig(png_buffer, format="png", dpi=80)
    png_buffer.seek(0)
    st.image(png_buffer)

    # PDF
    pdf_buffer = BytesIO()
    fig.savefig(pdf_buffer, format="pdf")
    pdf_buffer.seek(0)

    st.download_button(
        "Download sociogram som PDF",
        data=pdf_buffer,
        file_name="sociogram.pdf",
        mime="application/pdf",
    )
