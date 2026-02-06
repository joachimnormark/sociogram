import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Circle, FancyArrowPatch
import math
from io import BytesIO
import os
from datetime import datetime
from PIL import Image
import numpy as np

Image.MAX_IMAGE_PIXELS = None


# === CSV-læser ===
def read_csv_smart(file, header):
    for sep in [";", ",", "\t"]:
        file.seek(0)
        try:
            return pd.read_csv(file, sep=sep, header=header)
        except Exception:
            continue
    raise ValueError("Kunne ikke læse CSV-filen.")


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


# === Beregn præcis skæringspunkt mellem pil og ellipse ===
def ellipse_edge_point(cx, cy, x1, y1, x2, y2, width, height):
    """
    Finder punktet hvor linjen fra (x1,y1) mod (x2,y2)
    rammer ellipsen centreret i (cx,cy) med given width/height.
    """
    a = width / 2
    b = height / 2

    X1 = x1 - cx
    Y1 = y1 - cy
    dx = x2 - x1
    dy = y2 - y1

    A = (dx*dx)/(a*a) + (dy*dy)/(b*b)
    B = 2*((X1*dx)/(a*a) + (Y1*dy)/(b*b))
    C = (X1*X1)/(a*a) + (Y1*Y1)/(b*b) - 1

    disc = B*B - 4*A*C
    t = (-B + np.sqrt(disc)) / (2*A)

    ex = x1 + t*dx
    ey = y1 + t*dy
    return ex, ey


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

    if "elev" not in df.columns:
        st.error("Kunne ikke finde en kolonne med elevnavne.")
        st.stop()

    choice_cols = [c for c in df.columns if c != "elev"]
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
    positions = layout_circle(names) if layout_valg == "Cirkel-layout" else layout_grid(names)

    # Edges
    edges = []
    for _, row in df.iterrows():
        for c in choice_cols:
            edges.append((row["elev"], row[c]))

    mutual = {(a, b) for a, b in edges if (b, a) in edges}

    # === Tegn figur ===
    fig, ax = plt.subplots(figsize=(10, 10))

    R = 0.35
    node_width = R * 4.0
    node_height = R * 2.4

    def farve(n):
        if n <= 1:
            return "black"
        elif n < 3:
            return "red"
        elif n < 6:
            return "orange"
        else:
            return "green"

    # === Ovale noder ===
    for elev in names:
        x, y = positions[elev]

        ax.add_patch(
            Ellipse(
                (x, y),
                width=node_width,
                height=node_height,
                fill=False,
                edgecolor=farve(contacts_count[elev]),
                linewidth=2.5
            )
        )

        ax.text(x, y, elev, ha="center", va="center", fontsize=14)

    # === Pile ===
    for start, end in edges:
        x1, y1 = positions[start]
        x2, y2 = positions[end]

        # Startpunkt på start-ellipse
        sx, sy = ellipse_edge_point(x1, y1, x1, y1, x2, y2, node_width, node_height)

        # Slutpunkt på slut-ellipse
        ex, ey = ellipse_edge_point(x2, y2, x2, y2, x1, y1, node_width, node_height)

        color = "green" if (start, end) in mutual else "black"
        lw = 2 if (start, end) in mutual else 1

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

    # === Farveforklaring (vandret under grafen) ===
    legend_items = [
        ("Ingen peger på", "black"),
        ("Få valg (1-2)", "red"),
        ("Nogle valg (3-5)", "orange"),
        ("Mange valg (6+)", "green"),
    ]

    base_x = 0.10
    base_y = -0.08
    spacing_x = 0.25
    circle_r = 0.015

    for i, (label, color) in enumerate(legend_items):
        x = base_x + i * spacing_x
        y = base_y

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
