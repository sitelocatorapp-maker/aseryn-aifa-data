#!/usr/bin/env python3
import csv
import io
import json
import re
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

MEDS_URL = "https://drive.aifa.gov.it/farmaci/confezioni_fornitura.csv"
ACTIVE_URL = "https://drive.aifa.gov.it/farmaci/PA_confezioni.csv"

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SHARDS = PUBLIC / "shards"

def download(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ASERYN-AIFA-Builder/3.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = response.read()

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass

    raise RuntimeError(f"Impossibile decodificare {url}")

def norm(value):
    value = "" if value is None else str(value)
    value = unicodedata.normalize("NFD", value)
    value = "".join(
        c for c in value
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(
        r"[^a-zA-Z0-9]+",
        " ",
        value.lower(),
    ).strip()

def clean(value):
    if value is None:
        return None

    value = str(value).strip().strip('"')

    if not value or value.upper() in {"NULL", "N/A", "ND"}:
        return None

    return value

def detect_delimiter(text):
    try:
        return csv.Sniffer().sniff(
            text[:10000],
            delimiters=";,|\t",
        ).delimiter
    except Exception:
        return ";"

def rows(text):
    return csv.DictReader(
        io.StringIO(text),
        delimiter=detect_delimiter(text),
    )

def first(row, *names):
    upper = {
        str(key).strip().upper(): value
        for key, value in row.items()
    }

    for name in names:
        if name.upper() in upper:
            return clean(upper[name.upper()])

    return None

def encode_char(char):
    if "a" <= char <= "z":
        return char

    if char.isdigit():
        return "0"

    return "_"

def shard_key(name):
    compacted = re.sub(r"\s+", "", norm(name))

    chars = [
        compacted[0] if len(compacted) > 0 else "_",
        compacted[1] if len(compacted) > 1 else "_",
        compacted[2] if len(compacted) > 2 else "_",
    ]

    return "".join(encode_char(c) for c in chars)

def infer_unit_from_form(pharmaceutical_form):
    form = norm(pharmaceutical_form)

    if "compress" in form:
        return "compresse"
    if "capsul" in form:
        return "capsule"
    if "bustin" in form:
        return "bustine"
    if "fiala" in form:
        return "fiale"
    if "flacon" in form:
        return "flaconi"
    if "penna" in form:
        return "penne"
    if "cerott" in form:
        return "cerotti"
    if "suppost" in form:
        return "supposte"
    if "ovul" in form:
        return "ovuli"
    if "siring" in form:
        return "siringhe"

    return None

def infer_package_info(description, pharmaceutical_form):
    if not description:
        return None, infer_unit_from_form(pharmaceutical_form)

    text = norm(description)

    patterns = [
        (r"\b(\d+)\s*(?:x\s*1\s*)?(?:compresse|compressa|cpr)\b", "compresse"),
        (r"\b(\d+)\s+(?:capsule|capsula|cps)\b", "capsule"),
        (r"\b(\d+)\s+(?:bustine|bustina)\b", "bustine"),
        (r"\b(\d+)\s+(?:fiale|fiala)\b", "fiale"),
        (r"\b(\d+)\s+(?:flaconi|flacone)\b", "flaconi"),
        (r"\b(\d+)\s+(?:penne|penna)\b", "penne"),
        (r"\b(\d+)\s+(?:cerotti|cerotto)\b", "cerotti"),
        (r"\b(\d+)\s+(?:supposte|supposta)\b", "supposte"),
        (r"\b(\d+)\s+(?:ovuli|ovulo)\b", "ovuli"),
        (r"\b(\d+)\s+(?:siringhe|siringa)\b", "siringhe"),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            continue

        quantity = int(match.group(1))

        if quantity > 0:
            return quantity, unit

    return None, infer_unit_from_form(pharmaceutical_form)

def main():
    PUBLIC.mkdir(exist_ok=True)
    SHARDS.mkdir(parents=True, exist_ok=True)

    meds_text = download(MEDS_URL)
    active_text = download(ACTIVE_URL)

    active_by_aic = defaultdict(list)

    for row in rows(active_text):
        aic = first(row, "CODICE_AIC", "AIC")

        if not aic:
            continue

        ingredient = first(
            row,
            "PRINCIPIO_ATTIVO",
            "PA",
        )

        qty = first(row, "QUANTITA")
        unit = first(row, "UNITA_MISURA")

        if ingredient:
            active_by_aic[aic].append({
                "ingredient": ingredient,
                "qty": qty,
                "unit": unit,
            })

    shards = defaultdict(list)
    count = 0
    now = datetime.now(timezone.utc).isoformat()

    for row in rows(meds_text):
        aic = first(row, "CODICE_AIC", "AIC")
        name = first(row, "DENOMINAZIONE", "NOME")

        if not aic or not name:
            continue

        active_rows = active_by_aic.get(aic, [])
        ingredients = []
        strengths = []

        for active in active_rows:
            ingredient = active["ingredient"]

            if ingredient and ingredient not in ingredients:
                ingredients.append(ingredient)

            if active["qty"]:
                strength = active["qty"]

                if active["unit"]:
                    strength += f" {active['unit']}"

                if strength not in strengths:
                    strengths.append(strength)

        # Importante: niente search_text ridondante.
        # Il client lo calcola in memoria; così gli shard pesano molto meno.
        description = first(row, "DESCRIZIONE")
        pharmaceutical_form = first(row, "FORMA")
        package_quantity, package_unit = infer_package_info(
            description,
            pharmaceutical_form,
        )

        item = {
            "aic_code": aic,
            "name": name,
            "active_ingredient":
                " + ".join(ingredients)
                or first(row, "PA_ASSOCIATI"),
            "strength":
                " + ".join(strengths)
                or None,
            "pharmaceutical_form":
                pharmaceutical_form,
            "package_description":
                description,
            "package_quantity":
                package_quantity,
            "package_unit":
                package_unit,
            "company":
                first(row, "RAGIONE_SOCIALE"),
            "administrative_status":
                first(row, "STATO_AMMINISTRATIVO"),
            "atc_code":
                first(row, "CODICE_ATC"),
            "dosage_units": None,
            "supply_type":
                first(row, "FORNITURA"),
            "source_updated_at": None,
            "imported_at": now,
        }

        shards[shard_key(name)].append(item)
        count += 1

    for old in SHARDS.glob("*.json"):
        old.unlink()

    for key, items in shards.items():
        items.sort(
            key=lambda item: (
                norm(item["name"]),
                item["aic_code"],
            )
        )

        (SHARDS / f"{key}.json").write_text(
            json.dumps(
                items,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

    index = {
        "version": now[:10],
        "updated_at": now,
        "row_count": count,
        "shard_strategy": "first_three_name_characters_with_package_info",
        "shard_count": len(shards),
    }

    (PUBLIC / "index.json").write_text(
        json.dumps(
            index,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    print(
        f"Creati {len(shards)} shard "
        f"per {count} confezioni."
    )

if __name__ == "__main__":
    main()
