"""Hack the Highway: Enterprise Knowledge Graph & Ontology Engine.

This module models the operational domain of Wacky Wheels Co.:
- Plants, Models, Parts, Suppliers, Shipments, Part Lots
- Production Orders, Customer Orders, Customers, Dealers, Finished Vehicles
- Traversal logic to compute downstream impact blast radius and generate
  graph path reasoning evidence for each operational event.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
import csv
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple


START_DATE = date(2027, 3, 8)  # Monday, day index 0


def date_to_idx(d: date) -> int:
    days = (d - START_DATE).days
    if days % 7 > 4:
        raise ValueError(f"Date {d} falls on a weekend")
    return 5 * (days // 7) + (days % 7)


def idx_to_date(idx: int) -> date:
    return START_DATE + timedelta(days=7 * (idx // 5) + (idx % 5))


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@dataclass
class ImpactReport:
    """Standard deliverable container for event impact, evidence, and graph paths."""
    event_id: str
    category: str
    what_happened: str
    impact_summary: str
    reasoning_trace: List[str]
    graph_paths: List[str]
    affected_plants: List[str] = field(default_factory=list)
    affected_parts: List[str] = field(default_factory=list)
    affected_models: List[str] = field(default_factory=list)
    affected_production_orders: List[Dict[str, Any]] = field(default_factory=list)
    affected_customer_orders: List[Dict[str, Any]] = field(default_factory=list)
    affected_dealers: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    affected_customers: List[Dict[str, Any]] = field(default_factory=list)
    affected_lots: List[str] = field(default_factory=list)
    affected_vehicles_in_stock: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    affected_vehicles_sold: List[Dict[str, Any]] = field(default_factory=list)
    unconfirmed: bool = False
    is_noise: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "category": self.category,
            "what_happened": self.what_happened,
            "impact_summary": self.impact_summary,
            "reasoning_trace": self.reasoning_trace,
            "graph_paths": self.graph_paths,
            "affected_plants": self.affected_plants,
            "affected_parts": self.affected_parts,
            "affected_models": self.affected_models,
            "production_order_count": len(self.affected_production_orders),
            "customer_order_count": len(self.affected_customer_orders),
            "affected_dealers": dict(self.affected_dealers),
            "affected_customers_count": len(self.affected_customers),
            "affected_lots": self.affected_lots,
            "vehicles_in_stock_count": sum(len(v) for v in self.affected_vehicles_in_stock.values()),
            "vehicles_sold_count": len(self.affected_vehicles_sold),
            "unconfirmed": self.unconfirmed,
            "is_noise": self.is_noise,
        }


class KnowledgeGraph:
    """Enterprise Knowledge Graph representing Wacky Wheels Co.'s JIT manufacturing network."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._load_tables()
        self._build_indexes()

    def _load_tables(self):
        rd = lambda name: read_csv(os.path.join(self.data_dir, name))
        self.raw_plants = rd("plants.csv")
        self.raw_plant_models = rd("plant_models.csv")
        self.raw_models = rd("models.csv")
        self.raw_parts = rd("parts.csv")
        self.raw_bom = rd("bom.csv")
        self.raw_suppliers = rd("suppliers.csv")
        self.raw_shipments = rd("inbound_shipments.csv")
        self.raw_lots = rd("part_lots.csv")
        self.raw_orders = rd("production_orders.csv")
        self.raw_customer_orders = rd("customer_orders.csv")
        self.raw_customers = rd("customers.csv")
        self.raw_dealers = rd("dealers.csv")
        self.raw_loaners = rd("loaners.csv")
        self.raw_vehicles = rd("finished_vehicles.csv")
        self.raw_aliases = rd("aliases.csv")
        self.raw_calendar = rd("calendar.csv")

    def _build_indexes(self):
        # Plants: plant_id -> dict
        self.plants = {}
        for r in self.raw_plants:
            self.plants[r["plant_id"]] = {
                "plant_id": r["plant_id"],
                "name": r["name"],
                "city": r["city"],
                "slots_per_day": int(r["slots_per_day"]),
                "models": set(),
            }
        for r in self.raw_plant_models:
            if r["plant_id"] in self.plants:
                self.plants[r["plant_id"]]["models"].add(r["model"])

        # Models & BOM: model -> set(part_ids)
        self.models = {r["model"]: r for r in self.raw_models}
        self.bom = defaultdict(set)
        self.part_to_models = defaultdict(set)
        for r in self.raw_bom:
            self.bom[r["model"]].add(r["part_id"])
            self.part_to_models[r["part_id"]].add(r["model"])

        # Parts & Suppliers
        self.parts = {r["part_id"]: r for r in self.raw_parts}
        self.suppliers = {r["supplier_id"]: r for r in self.raw_suppliers}

        # Shipments: shipment_id -> dict
        self.shipments = {r["shipment_id"]: r for r in self.raw_shipments}
        # Inbound shipments indexed by (part_id, plant_id, eta_date)
        self.shipments_by_part_plant_eta = defaultdict(list)
        for r in self.raw_shipments:
            self.shipments_by_part_plant_eta[(r["part_id"], r["plant_id"], r["eta_date"])].append(r)

        # Part lots: lot_id -> dict and lookup by (part_id, plant_id, first_build_date, last_build_date)
        self.lots = {r["lot_id"]: r for r in self.raw_lots}

        # Production orders: po_id -> dict
        self.production_orders = {}
        self.orders_by_plant_date = defaultdict(list)
        for r in self.raw_orders:
            po = {
                "production_order_id": r["production_order_id"],
                "plant_id": r["plant_id"],
                "build_date": r["build_date"],
                "model": r["model"],
                "units": int(r["units"]),
            }
            self.production_orders[r["production_order_id"]] = po
            self.orders_by_plant_date[(r["plant_id"], r["build_date"])].append(po)

        # Customer orders: co_id -> dict and po_id -> list[co_id]
        self.customer_orders = {r["customer_order_id"]: r for r in self.raw_customer_orders}
        self.cos_by_po = defaultdict(list)
        for r in self.raw_customer_orders:
            self.cos_by_po[r["production_order_id"]].append(r)

        # Customers & Dealers
        self.customers = {r["customer_id"]: r for r in self.raw_customers}
        self.dealers = {r["dealer_id"]: r for r in self.raw_dealers}
        self.loaners = {r["dealer_id"]: int(r["loaners_available"]) for r in self.raw_loaners}

        # Finished vehicles: vin -> dict and lookups
        self.vehicles = {r["vin"]: r for r in self.raw_vehicles}
        self.vehicles_by_plant_date_model = defaultdict(list)
        for r in self.raw_vehicles:
            self.vehicles_by_plant_date_model[(r["plant_id"], r["build_date"], r["model"])].append(r)

        # Aliases: text phrase -> (entity_type, entity_id)
        self.aliases = {}
        for r in self.raw_aliases:
            self.aliases[r["alias"].strip().lower()] = (r["entity_type"], r["entity_id"])

        # Calendar: date string <-> index, weekday
        self.calendar_by_date = {r["date"]: r for r in self.raw_calendar}
        self.calendar_by_idx = {int(r["day_index"]): r for r in self.raw_calendar}

    # -------------------------------------------------------------------------
    # Resolution Helpers
    # -------------------------------------------------------------------------
    def resolve_entity(self, text_or_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolves an alias or ID to (entity_type, entity_id)."""
        clean = text_or_id.strip()
        lower = clean.lower()
        if lower in self.aliases:
            return self.aliases[lower]
        # Check direct entity matches
        if clean in self.plants:
            return "plant", clean
        if clean in self.parts:
            return "part", clean
        if clean in self.suppliers:
            return "supplier", clean
        if clean in self.models:
            return "model", clean
        if clean in self.shipments:
            return "shipment", clean
        if clean in self.lots:
            return "lot", clean
        if clean in self.dealers:
            return "dealer", clean
        return None, None

    def find_matching_shipment(
        self,
        part_id: str,
        plant_id: str,
        orig_eta: str,
        supplier_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        candidates = self.shipments_by_part_plant_eta.get((part_id, plant_id, orig_eta), [])
        if supplier_id:
            filtered = [s for s in candidates if s["supplier_id"] == supplier_id]
            if filtered:
                return filtered[0]
        return candidates[0] if candidates else None

    def find_matching_lot(
        self,
        part_id: str,
        plant_id: str,
        start_date: str,
        end_date: str,
        supplier_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        for lot in self.lots.values():
            if lot["part_id"] == part_id and lot["plant_id"] == plant_id:
                if lot["first_build_date"] == start_date and lot["last_build_date"] == end_date:
                    if supplier_id and lot["supplier_id"] != supplier_id:
                        continue
                    return lot
        return None

    # -------------------------------------------------------------------------
    # Graph Traversal 1: Supplier Delay
    # -------------------------------------------------------------------------
    def traverse_supplier_delay(
        self,
        event_id: str,
        plant_id: str,
        part_id: str,
        orig_eta: str,
        new_eta: str,
        shipment_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
    ) -> ImpactReport:
        """
        Traverses:
        Shipment -> Part -> Model (via BOM) -> ProductionOrder -> CustomerOrder -> Dealer / Customer.
        Rule 1: Builds that need the part cannot run from orig_eta up to (not including) new_eta.
        Only at the receiving plant.
        """
        trace = []
        paths = []

        # 1. Resolve shipment
        shipment = None
        if shipment_id and shipment_id in self.shipments:
            shipment = self.shipments[shipment_id]
        else:
            shipment = self.find_matching_shipment(part_id, plant_id, orig_eta, supplier_id)
            if shipment:
                shipment_id = shipment["shipment_id"]

        shipment_label = shipment_id if shipment_id else f"Shipment({part_id}@{plant_id})"
        trace.append(f"Identified inbound shipment {shipment_label} delayed from {orig_eta} to {new_eta}.")

        # 2. Part & BOM Models
        part_name = self.parts.get(part_id, {}).get("name", part_id)
        affected_models = sorted(list(self.part_to_models.get(part_id, set())))
        trace.append(f"Part {part_id} ({part_name}) is required in BOM of models: {', '.join(affected_models)}.")

        # 3. Find affected production orders at receiving plant in [orig_eta, new_eta)
        orig_d = date.fromisoformat(orig_eta)
        new_d = date.fromisoformat(new_eta)
        curr_d = orig_d
        affected_pos = []

        while curr_d < new_d:
            if curr_d.weekday() < 5:  # Monday to Friday
                d_str = curr_d.isoformat()
                for po in self.orders_by_plant_date.get((plant_id, d_str), []):
                    if po["model"] in affected_models:
                        affected_pos.append(po)
            curr_d += timedelta(days=1)

        trace.append(
            f"Found {len(affected_pos)} production orders at {plant_id} between {orig_eta} and {new_eta} requiring {part_id}."
        )

        # 4. Find affected customer orders, dealers, customers
        affected_cos = []
        dealers_map = defaultdict(list)
        customers_list = []

        for po in affected_pos:
            cos = self.cos_by_po.get(po["production_order_id"], [])
            for co in cos:
                affected_cos.append(co)
                dealers_map[co["dealer_id"]].append(co["customer_order_id"])
                cust = self.customers.get(co["customer_id"], {})
                customers_list.append({
                    "customer_id": co["customer_id"],
                    "customer_order_id": co["customer_order_id"],
                    "dealer_id": co["dealer_id"],
                    "tier": cust.get("tier", "Standard"),
                    "name": cust.get("name", "Unknown"),
                    "promised_date": co["promised_date"],
                })
                # Emit graph path for each affected customer order
                paths.append(
                    f"Shipment({shipment_label}) → Part({part_id}) → Model({po['model']}) [BOM] → "
                    f"ProductionOrder({po['production_order_id']}) [{po['build_date']}] → "
                    f"CustomerOrder({co['customer_order_id']}) → Dealer({co['dealer_id']}) / Customer({co['customer_id']})"
                )

        what_happened = (
            f"Supplier delay: Shipment {shipment_label} of {part_id} for plant {plant_id} delayed from "
            f"{orig_eta} to {new_eta}."
        )
        impact_summary = (
            f"{len(affected_pos)} production orders halted at {plant_id}; {len(affected_cos)} customer orders "
            f"impacted across {len(dealers_map)} dealers."
        )

        return ImpactReport(
            event_id=event_id,
            category="Supplier Delay",
            what_happened=what_happened,
            impact_summary=impact_summary,
            reasoning_trace=trace,
            graph_paths=paths,
            affected_plants=[plant_id],
            affected_parts=[part_id],
            affected_models=affected_models,
            affected_production_orders=affected_pos,
            affected_customer_orders=affected_cos,
            affected_dealers=dealers_map,
            affected_customers=customers_list,
        )

    # -------------------------------------------------------------------------
    # Graph Traversal 2: Plant Outage
    # -------------------------------------------------------------------------
    def traverse_plant_outage(
        self,
        event_id: str,
        plant_id: str,
        start_date: str,
        end_date: str,
    ) -> ImpactReport:
        """
        Traverses:
        Plant -> ProductionOrder -> CustomerOrder -> Dealer / Customer.
        Rule 2: No builds at plant during outage (inclusive). All production orders in range are affected.
        """
        trace = []
        paths = []
        plant_name = self.plants.get(plant_id, {}).get("name", plant_id)
        trace.append(f"Plant outage confirmed at {plant_id} ({plant_name}) from {start_date} to {end_date} (inclusive).")

        start_d = date.fromisoformat(start_date)
        end_d = date.fromisoformat(end_date)
        curr_d = start_d
        affected_pos = []

        while curr_d <= end_d:
            if curr_d.weekday() < 5:
                d_str = curr_d.isoformat()
                for po in self.orders_by_plant_date.get((plant_id, d_str), []):
                    affected_pos.append(po)
            curr_d += timedelta(days=1)

        trace.append(f"Found {len(affected_pos)} production orders halted at {plant_id} during outage dates.")

        affected_cos = []
        dealers_map = defaultdict(list)
        customers_list = []
        affected_models = set()

        for po in affected_pos:
            affected_models.add(po["model"])
            cos = self.cos_by_po.get(po["production_order_id"], [])
            for co in cos:
                affected_cos.append(co)
                dealers_map[co["dealer_id"]].append(co["customer_order_id"])
                cust = self.customers.get(co["customer_id"], {})
                customers_list.append({
                    "customer_id": co["customer_id"],
                    "customer_order_id": co["customer_order_id"],
                    "dealer_id": co["dealer_id"],
                    "tier": cust.get("tier", "Standard"),
                    "name": cust.get("name", "Unknown"),
                    "promised_date": co["promised_date"],
                })
                paths.append(
                    f"Plant({plant_id}) → ProductionOrder({po['production_order_id']}) [{po['model']} on {po['build_date']}] → "
                    f"CustomerOrder({co['customer_order_id']}) → Dealer({co['dealer_id']}) / Customer({co['customer_id']})"
                )

        what_happened = f"Plant outage: {plant_name} ({plant_id}) shutdown from {start_date} to {end_date} inclusive."
        impact_summary = (
            f"{len(affected_pos)} production orders halted; {len(affected_cos)} customer orders impacted "
            f"across {len(dealers_map)} dealers."
        )

        return ImpactReport(
            event_id=event_id,
            category="Plant Outage",
            what_happened=what_happened,
            impact_summary=impact_summary,
            reasoning_trace=trace,
            graph_paths=paths,
            affected_plants=[plant_id],
            affected_models=sorted(list(affected_models)),
            affected_production_orders=affected_pos,
            affected_customer_orders=affected_cos,
            affected_dealers=dealers_map,
            affected_customers=customers_list,
        )

    # -------------------------------------------------------------------------
    # Graph Traversal 3: Quality Hold
    # -------------------------------------------------------------------------
    def traverse_quality_hold(
        self,
        event_id: str,
        plant_id: str,
        part_id: str,
        start_date: str,
        end_date: str,
        lot_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
    ) -> ImpactReport:
        """
        Traverses:
        Lot -> ProductionOrder -> FinishedVehicle -> Dealer (in_stock) / Customer (sold).
        Rule 6: Hold lot. Quarantines finished vehicles built at plant during build dates
        from models that use the part. Unsold -> stop_sale; Sold -> notify_customer.
        """
        trace = []
        paths = []

        # 1. Resolve Lot
        if lot_id and lot_id in self.lots:
            lot = self.lots[lot_id]
        else:
            lot = self.find_matching_lot(part_id, plant_id, start_date, end_date, supplier_id)
            if lot:
                lot_id = lot["lot_id"]
            else:
                raise ValueError(f"Could not resolve lot for {part_id} at {plant_id} between {start_date} and {end_date}")

        trace.append(f"Identified defective part lot {lot_id} (Part: {part_id}, Plant: {plant_id}, Dates: {start_date}..{end_date}).")

        # 2. Identify Models that use this part via BOM
        affected_models = self.part_to_models.get(part_id, set())
        trace.append(f"Part {part_id} is in BOM of models: {', '.join(sorted(affected_models))}.")

        # 3. Find Finished Vehicles built at plant, during build dates, of affected models
        start_d = date.fromisoformat(start_date)
        end_d = date.fromisoformat(end_date)
        curr_d = start_d
        affected_vins = []

        while curr_d <= end_d:
            if curr_d.weekday() < 5:
                d_str = curr_d.isoformat()
                for model in affected_models:
                    vehicles = self.vehicles_by_plant_date_model.get((plant_id, d_str, model), [])
                    affected_vins.extend(vehicles)
            curr_d += timedelta(days=1)

        trace.append(f"Discovered {len(affected_vins)} finished vehicles produced with suspect lot {lot_id}.")

        # 4. Split into Unsold (in_stock at dealer) vs Sold (with customer)
        in_stock_by_dealer = defaultdict(list)
        sold_vehicles = []

        for v in affected_vins:
            vin = v["vin"]
            status = v["status"]
            po_id = v["production_order_id"]
            if status == "in_stock":
                in_stock_by_dealer[v["dealer_id"]].append(vin)
                paths.append(
                    f"Lot({lot_id}) → ProductionOrder({po_id}) → Vehicle({vin}) [in_stock] → Dealer({v['dealer_id']})"
                )
            elif status == "sold":
                cust = self.customers.get(v["customer_id"], {})
                sold_vehicles.append({
                    "vin": vin,
                    "production_order_id": po_id,
                    "customer_id": v["customer_id"],
                    "customer_name": cust.get("name", "Unknown"),
                    "dealer_id": v["dealer_id"],
                })
                paths.append(
                    f"Lot({lot_id}) → ProductionOrder({po_id}) → Vehicle({vin}) [sold] → Customer({v['customer_id']})"
                )

        what_happened = f"Quality alert: Defective lot {lot_id} ({part_id}) at {plant_id} built between {start_date} and {end_date}."
        impact_summary = (
            f"Lot {lot_id} requires quarantine. {sum(len(v) for v in in_stock_by_dealer.values())} unsold vehicles held "
            f"across {len(in_stock_by_dealer)} dealers; {len(sold_vehicles)} vehicle owners require safety notification."
        )

        return ImpactReport(
            event_id=event_id,
            category="Quality Hold",
            what_happened=what_happened,
            impact_summary=impact_summary,
            reasoning_trace=trace,
            graph_paths=paths,
            affected_plants=[plant_id],
            affected_parts=[part_id],
            affected_models=sorted(list(affected_models)),
            affected_lots=[lot_id],
            affected_vehicles_in_stock=in_stock_by_dealer,
            affected_vehicles_sold=sold_vehicles,
        )

    # -------------------------------------------------------------------------
    # Graph Traversal 4: Noise
    # -------------------------------------------------------------------------
    def traverse_noise(self, event_id: str, reason: str) -> ImpactReport:
        return ImpactReport(
            event_id=event_id,
            category="Noise",
            what_happened="Non-operational message received.",
            impact_summary="Event determined to be irrelevant noise; zero enterprise state modifications.",
            reasoning_trace=[
                f"Knowledge graph semantic check: Event classified as Noise. Reason: {reason}.",
                "Policy rule 7 applied: Zero write actions taken on enterprise systems."
            ],
            graph_paths=["None (No operational entities impacted)"],
            is_noise=True,
        )

    # -------------------------------------------------------------------------
    # Graph Traversal 5: Unconfirmed Rumor
    # -------------------------------------------------------------------------
    def traverse_unconfirmed(self, event_id: str, reason: str) -> ImpactReport:
        return ImpactReport(
            event_id=event_id,
            category="Unconfirmed Report",
            what_happened="Unconfirmed operational rumor received.",
            impact_summary="Report lacks verifiable entities or dates; escalated to Human-in-the-Loop operator.",
            reasoning_trace=[
                f"Knowledge graph validation check: Rumor lacks specific verifiable identifiers. Reason: {reason}.",
                "Policy rule 8 applied: Hand off to human operator via escalate tool; zero operational modifications."
            ],
            graph_paths=["None (Escalated to human supervisor prior to graph modification)"],
            unconfirmed=True,
        )

    # -------------------------------------------------------------------------
    # UI & Visualization Export
    # -------------------------------------------------------------------------
    def export_graph_summary(self) -> Dict[str, Any]:
        """Provides high-level graph topology statistics for UI / design card."""
        return {
            "node_counts": {
                "plants": len(self.plants),
                "models": len(self.models),
                "parts": len(self.parts),
                "suppliers": len(self.suppliers),
                "shipments": len(self.shipments),
                "lots": len(self.lots),
                "production_orders": len(self.production_orders),
                "customer_orders": len(self.customer_orders),
                "customers": len(self.customers),
                "dealers": len(self.dealers),
                "vehicles": len(self.vehicles),
            },
            "edge_types": [
                "BUILDS (Plant -> Model)",
                "REQUIRES (Model -> Part via BOM)",
                "SUPPLIES (Supplier -> Part)",
                "CARRIES (Shipment -> Part)",
                "SCHEDULED_AT (ProductionOrder -> Plant)",
                "ASSIGNED_TO (CustomerOrder -> ProductionOrder)",
                "STOCKED_AT (Vehicle -> Dealer)",
                "OWNED_BY (Vehicle -> Customer)",
                "PRODUCED_FROM_LOT (Vehicle -> Lot)",
            ]
        }
