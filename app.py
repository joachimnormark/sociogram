import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
import math
from io import BytesIO

st.title("Sociogram-generator")

st.write("Upload en CSV-fil med kolonnerne: **Elev, 1, 2, 3**")

uploaded_file = st.file_uploader("Vælg CSV-fil", type=["csv"])

if uploaded_file is not None:
    # Læs data – automatisk separator (komma eller semikolon)
    df = pd.read_csv(uploaded_file, sep=None, engine="python")

    # Normaliser kolonnenavne
    df.columns = df.columns.str.strip().str.lower()

    # Krævede kolonner
    required_cols = {"elev", "1", "2", "3"}
    if not required_cols.issubset(set(df.columns)):
        st.error(f"Filen skal indeholde kolonnerne: {required_cols}. Jeg fandt: {list(df.columns)}")
        st.stop()

    # Tjek: alle elever skal pege på 3 andre (ingen manglende værdier i 1, 2, 3)
    if df[["1", "2", "3"]].isna().any().any():
        st.error("En elev peger ikke på 3 andre, og derfor kan sociogrammet ikke laves.")
        st.stop()

    # Tjek: ingen elev må pege på sig selv
    self_reference_found = False
    for _, row in df.iterrows():
        elev = str(row["elev"]).strip().lower()
        valg1 = str(row["1"]).strip().lower()
        valg2 = str(row["2"]).strip().lower()
        valg3 = str(row["3"]).strip().lower()
        if elev in {valg1, valg2, valg3}:
            self_reference_found = True
            break

    if self_reference_found:
        st.error("En elev peger på sig selv, og derfor kan sociogrammet ikke laves.")
        st.stop()

    # === 2. Beregn antal kontakter pr. elev ===
    all_names = pd.concat([df["elev"], df["1"], df["2"], df["3"]])
    contacts_count = all_names.value_counts().to_dict()

    # === 3. Opret positionslayout (cirkel) ===
    nodes = {}
    n = len(contacts_count)
    radius_circle = 5
    for i, elev in enumerate(contacts_count.keys()):
        angle = 2 * math.pi * i / n
        x = radius_circle * math.cos(angle)
        y = radius_circle * math.sin(angle)
        nodes[elev] = {"pos": (x, y), "contacts": contacts_count[elev]}

    # === 4. Opret forbindelser (edges) ===
    edges = []
    for _, row in df.iterrows():
        elev = str(row["elev"]).strip()
        valg1 = str(row["1"]).strip()
        valg2 = str(row["2"]).strip()
        valg3 = str(row["3"]).strip()

        edges.append((elev, valg1))
        edges.append((elev, valg2))
        edges.append((elev, valg3))

    # Find gensidige relationer (dobbeltpile)
    mutual_edges = set()
    for a, b in edges:
        if (b, a) in edges:
            mutual_edges.add((a, b))
            mutual_edges.add((b, a))

    # === 5. Tegn diagram ===
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_xlim(-radius_circle - 2, radius_circle + 2)
    ax.set_ylim(-radius_circle - 2, radius_circle + 2)
    ax.set_aspect("equal")

    # Funktion til farvekodning
    def get_color(n):
        if n < 3:
            return "red"
        elif n < 6:
            return "orange"
        else:
            return "green"

    # Tegn cirkler for hver elev
    for elev, data in nodes.items():
        x, y = data["pos"]
        r = 0.3 + data["contacts"] * 0.05
        circle = Circle((x, y), r, color=get_color(data["contacts"]), ec="black", zorder=2)
        ax.add_patch(circle)
        ax.text(x, y, elev, ha="center", va="center", fontsize=10, zorder=3)

    # Tegn pile mellem elever
    for start, end in edges:
        if start not in nodes or end not in nodes:
            continue

        x1, y1 = nodes[start]["pos"]
        x2, y2 = nodes[end]["pos"]
        r_start = 0.3 + nodes[start]["contacts"] * 0.05
        r_end = 0.3 + nodes[end]["contacts"] * 0.05

        dx, dy = x2 - x1, y2 - y1
        dist = math.sqrt(dx**2 + dy**2)

        # Her burde dist aldrig være 0 pga. tjekket for selv-reference,
        # men vi kan være ekstra defensive:
        if dist == 0:
            continue

        offset_start = r_start / dist
        offset_end = r_end / dist

        new_x1 = x1 + dx * offset_start
        new_y1 = y1 + dy * offset_start
        new_x2 = x2 - dx * offset_end
        new_y2 = y2 - dy * offset_end

        if (start, end) in mutual_edges:
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

    # === 6. Titel og legend ===
    plt.title("Sociogram")
    legend_elements = [
        Circle((0, 0), 0.3, color="red", label="Ingen peger på"),
        Circle((0, 0), 0.3, color="orange", label="Nogle peger på (1-3)"),
        Circle((0, 0), 0.3, color="green", label="Mange peger på (4+)"),
    ]
    ax.legend(handles=legend_elements, loc="upper right")
    plt.axis("off")

    # Vis figuren i Streamlit
    st.pyplot(fig)

    # Gem som PDF i hukommelsen
    pdf_buffer = BytesIO()
    fig.savefig(pdf_buffer, format="pdf")
    pdf_buffer.seek(0)

    st.download_button(
        label="Download sociogram som PDF",
        data=pdf_buffer,
        file_name="sociogram.pdf",
        mime="application/pdf",
    )
