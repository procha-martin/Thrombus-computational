from pathlib import Path
import xml.etree.ElementTree as ET
import shutil

def write_coeffs(
    template_feb,
    output_feb,
    coeffs,
    material_id="1"
):
    template_feb = Path(template_feb)
    output_feb = Path(output_feb)

    shutil.copy(template_feb, output_feb)

    tree = ET.parse(output_feb)
    root = tree.getroot()

    material = root.find(f".//material[@id='{material_id}']")
    if material is None:
        raise KeyError(f"Material id={material_id} not found")

    for name, value in coeffs.items():
        elem = material.find(name)
        if elem is None:
            raise KeyError(f"Tag <{name}> not found in material {material_id}")
        elem.text = str(value)

    tree.write(
        output_feb,
        encoding="ISO-8859-1",
        xml_declaration=True
    )
