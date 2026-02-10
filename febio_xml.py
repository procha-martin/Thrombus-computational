import re
from pathlib import Path
import xml.etree.ElementTree as ET

_num_re = re.compile(r"\d+")

def extract_surface_node_ids(feb_path: Path, surface_name: str) -> list[int]:
    """
    Extract unique node IDs used in a <Surface name="..."> block.
    Works for quad4/tri3/etc elements listed like: <quad4>n1,n2,n3,n4</quad4>
    """
    text = Path(feb_path).read_text(errors="ignore")

    # Find the surface block
    start_tag = f'<Surface name="{surface_name}">'
    start = text.find(start_tag)
    if start == -1:
        raise ValueError(f"Surface '{surface_name}' not found in {feb_path}")

    end = text.find("</Surface>", start)
    if end == -1:
        raise ValueError(f"Surface '{surface_name}' block not closed in {feb_path}")

    block = text[start:end]

    # Grab all integers inside the block (includes quad ids too)
    nums = [int(x) for x in _num_re.findall(block)]

    # The first integers are quad4 ids too, but that’s fine—filter them out:
    # Node IDs in your mesh are > 0; quad ids also >0 so we need a better filter.
    # Better approach: only parse inside element tags lines.
    node_ids = set()
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("<") and ">" in line and "</" in line:
            # content between > and <
            content = line.split(">", 1)[1].rsplit("<", 1)[0]
            # content looks like "5,35,522,108"
            for n in _num_re.findall(content):
                node_ids.add(int(n))

    return sorted(node_ids)

def read_coeffs_from_feb(feb_path, names):
    """
    Returns coefficients as a list of floats, in the same order as `names`.
    """
    feb_path = Path(feb_path)
    tree = ET.parse(feb_path)
    root = tree.getroot()

    coeffs = []
    for tag in names:
        elem = root.find(f".//{tag}")
        if elem is None or elem.text is None:
            raise ValueError(f"Tag <{tag}> not found in {feb_path}")
        coeffs.append(float(elem.text.strip()))

    return coeffs


def write_coeffs_to_feb(feb_path, names, values):
    """
    Overwrite coefficient tags with new numeric values.
    """
    feb_path = Path(feb_path)
    tree = ET.parse(feb_path)
    root = tree.getroot()

    for tag, val in zip(names, values):
        elems = root.findall(f".//{tag}")
        if not elems:
            raise ValueError(f"Tag <{tag}> not found in {feb_path}")

        for elem in elems:
            elem.text = f"{val:.9g}"

    tree.write(feb_path, encoding="utf-8", xml_declaration=True)


def update_logfile_path(feb_path, reaction_file_path):
    """
    Update ONLY the 'file' attribute of an existing <logfile> tag.
    """
    feb_path = Path(feb_path)
    tree = ET.parse(feb_path)
    root = tree.getroot()

    node = root.find(".//logfile") or root.find(".//Logfile")
    if node is None:
        print(f"Warning: no <logfile> tag found in {feb_path}")
        return

    node.set("file", str(reaction_file_path))
    tree.write(feb_path, encoding="utf-8", xml_declaration=True)


def get_logfile_path(feb_path):
    """
    Return the logfile 'file' attribute, or empty string if missing.
    """
    feb_path = Path(feb_path)
    tree = ET.parse(feb_path)
    root = tree.getroot()

    node = root.find(".//logfile") or root.find(".//Logfile")
    if node is None:
        return ""

    return node.attrib.get("file", "")

def update_log_data_file(feb_path: Path, tag: str, data_name: str, new_file: Path):
    """
    Update <node_data data="Rx" file="..."> or <element_data data="sx" file="...">
    inside the <logfile> section.
    """
    feb_path = Path(feb_path)
    tree = ET.parse(feb_path)
    root = tree.getroot()

    logfile = root.find(".//logfile") or root.find(".//Logfile")
    if logfile is None:
        raise ValueError("No <logfile> section found in FEB file")

    found = False
    for node in logfile.findall(f".//{tag}"):
        if node.attrib.get("data") == data_name:
            node.set("file", Path(new_file).name)
            found = True

    if not found:
        raise ValueError(f"No <{tag} data='{data_name}'> found in logfile")

    tree.write(feb_path, encoding="utf-8", xml_declaration=True)