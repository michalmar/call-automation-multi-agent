from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent.parent
SOURCE_XLSX = ROOT / "Ciselnik.xlsx"
OUTPUT_JSON = ROOT / "public" / "data" / "stations.json"
MAIN_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def normalize_text(value: str) -> str | None:
    cleaned = (value or "").strip()
    if cleaned in {"", "-"}:
        return None
    return cleaned


def parse_deg(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.strip().replace("°", "").replace(",", ".")
    if cleaned and cleaned[0] in {"N", "E", "S", "W"}:
        cleaned = cleaned[1:]
    if not cleaned:
        return None
    number = float(cleaned)
    if value.strip().startswith(("S", "W")):
        number *= -1
    return round(number, 6)


def parse_number(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.strip().replace(",", ".")
    if cleaned in {"", "-"}:
        return None
    return float(cleaned) if cleaned else None


def get_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("main:si", MAIN_NS):
        text = "".join(node.text or "" for node in item.iterfind(".//main:t", MAIN_NS))
        values.append(text)
    return values


def read_rows() -> list[dict[str, str]]:
    with ZipFile(SOURCE_XLSX) as archive:
        shared_strings = get_shared_strings(archive)
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = sheet.findall(".//main:sheetData/main:row", MAIN_NS)
        parsed_rows: list[dict[str, str]] = []

        for row in rows:
            values: dict[str, str] = {}
            for cell in row.findall("main:c", MAIN_NS):
                ref = "".join(ch for ch in cell.attrib.get("r", "") if ch.isalpha())
                raw_value = cell.find("main:v", MAIN_NS)
                value = raw_value.text if raw_value is not None and raw_value.text else ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared_strings[int(value)]
                values[ref] = value
            parsed_rows.append(values)

    return parsed_rows


def build_station_records(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    if not rows:
        raise RuntimeError("Workbook is empty.")

    header_row = rows[0]
    labels = {column: title for column, title in header_row.items()}
    station_records: list[dict[str, object]] = []

    for row in rows[1:]:
        qualifier = row.get("L")
        if qualifier not in {"1", "61"}:
            continue

        lat = parse_deg(row.get("Z"))
        lng = parse_deg(row.get("AA"))
        if lat is None or lng is None:
            continue

        primary_name = normalize_text(row.get("B"))
        display_name = normalize_text(row.get("K"))

        record = {
            "id": row.get("A"),
            "name": primary_name or display_name or row.get("A"),
            "foreignName": normalize_text(row.get("C")),
            "nameShort": normalize_text(row.get("D")),
            "displayName": display_name or primary_name or row.get("A"),
            "qualifierCode": qualifier,
            "qualifierLabel": normalize_text(row.get("M")) or labels.get("M"),
            "status": normalize_text(row.get("O")) or "Neuvedeno",
            "kmPosition": parse_number(row.get("P")),
            "tudu": normalize_text(row.get("Q")),
            "ttp": normalize_text(row.get("R")),
            "lat": lat,
            "lng": lng,
            "elevation": parse_number(row.get("AB")),
            "regionCode": normalize_text(row.get("AC")),
            "region": normalize_text(row.get("AD")) or "Neuvedeno",
            "owner": normalize_text(row.get("AE")),
            "operator": normalize_text(row.get("AF")) or "Neuvedeno",
            "operatingDistrict": normalize_text(row.get("AH")),
            "directorate": normalize_text(row.get("AJ")),
            "operationsControl": normalize_text(row.get("AL")),
            "node": normalize_text(row.get("AN")),
            "remoteControl": normalize_text(row.get("AP")),
        }
        station_records.append(record)

    station_records.sort(key=lambda item: (str(item["name"]).casefold(), str(item["id"])))
    return station_records


def main() -> None:
    if not SOURCE_XLSX.exists():
        raise FileNotFoundError(f"Missing workbook: {SOURCE_XLSX}")

    rows = read_rows()
    stations = build_station_records(rows)
    if not stations:
        raise RuntimeError("No records matched Kvalifikátor values 1 or 61.")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(stations, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {len(stations)} stations to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
