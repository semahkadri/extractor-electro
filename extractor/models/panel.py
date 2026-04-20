from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PuissanceICTRow(BaseModel):
    """One row of the Puissance ICT table (zones B-C, C-A, or A-B)."""

    zone_tension: str = Field(..., description="Tension zone: B-C, C-A, or A-B")
    tension_primaire_v: float = Field(..., ge=0, le=1000)
    zone_courant_primaire: str = Field(..., description="Courant primaire zone: A, B, or C")
    courant_primaire_a: float = Field(..., ge=0, le=500)
    zone_courant_secondaire: str = Field(..., description="Courant secondaire zone: A, B, or C")
    courant_secondaire_a: float = Field(..., ge=0, le=500)

    @field_validator("zone_tension")
    @classmethod
    def _validate_zone_tension(cls, v: str) -> str:
        v = v.upper().strip().replace(" ", "")
        if v not in {"B-C", "C-A", "A-B"}:
            raise ValueError(f"Invalid zone_tension: {v}")
        return v

    @field_validator("zone_courant_primaire", "zone_courant_secondaire")
    @classmethod
    def _validate_zone_courant(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in {"A", "B", "C"}:
            raise ValueError(f"Invalid zone_courant: {v}")
        return v


class AccelerateurZone(BaseModel):
    """One row of the Accelerateurs table (zone A or B)."""

    zone: str = Field(..., description="Zone: A or B")
    r_icol_kv: float = Field(..., ge=0, le=2000)
    courant_colonne_ua: float = Field(..., ge=0, le=1000)
    vide_torr: str = Field(..., description="Scientific notation, e.g. '4.8e-007'")
    courant_aperture_ua: float = Field(..., ge=0, le=1000)

    @field_validator("zone")
    @classmethod
    def _validate_zone(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in {"A", "B"}:
            raise ValueError(f"Invalid zone: {v}")
        return v

    @field_validator("vide_torr")
    @classmethod
    def _validate_vide(cls, v: str) -> str:
        # Normalize: scientific notation uses dot universally
        v = v.replace(",", ".")
        try:
            float(v)
        except ValueError:
            raise ValueError(f"Invalid vide_torr: {v}")
        return v


class AccelerateurGlobal(BaseModel):
    """Global accelerator readings."""

    tension_kv: float = Field(..., ge=0, le=2000)
    charge_ma: float = Field(..., ge=0, le=500)
    faisceau_ma_a: float = Field(..., ge=0, le=200)
    faisceau_ma_b: float = Field(..., ge=0, le=200)


class PanelData(BaseModel):
    """Complete validated extraction from one panel screenshot."""

    puissance_ict: list[PuissanceICTRow] = Field(..., min_length=3, max_length=3)
    accelerateurs_zones: list[AccelerateurZone] = Field(..., min_length=2, max_length=2)
    accelerateurs_global: AccelerateurGlobal

    @field_validator("puissance_ict")
    @classmethod
    def _validate_puissance(cls, v: list[PuissanceICTRow]) -> list[PuissanceICTRow]:
        zones = {r.zone_tension for r in v}
        if zones != {"B-C", "C-A", "A-B"}:
            raise ValueError(f"Expected zones B-C/C-A/A-B, got {zones}")
        return v

    @field_validator("accelerateurs_zones")
    @classmethod
    def _validate_accel(cls, v: list[AccelerateurZone]) -> list[AccelerateurZone]:
        zones = {r.zone for r in v}
        if zones != {"A", "B"}:
            raise ValueError(f"Expected zones A/B, got {zones}")
        return v
