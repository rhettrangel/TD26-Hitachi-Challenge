# Enterprise Knowledge Graph & Ontology Diagram

**Company:** Wacky Wheels Co.  
**System:** Autonomous JIT Multi-Agent Control Tower  

---

## 1. High-Level Entity-Relationship Schema

The enterprise ontology models all manufacturing entities and their operational dependencies. Below is the full schema diagram:

```mermaid
graph TD
    Supplier["Supplier (18)"] -->|SUPPLIES| Part["Part (20)"]
    Shipment["Shipment (364)"] -->|CARRIES| Part
    Shipment -->|DESTINED_FOR| Plant["Assembly Plant (6)"]
    
    Model["Vehicle Model (6)"] -->|REQUIRES (BOM)| Part
    Plant -->|BUILDS| Model
    
    ProductionOrder["Production Order (540)"] -->|SCHEDULED_AT| Plant
    ProductionOrder -->|PRODUCES| Model
    
    CustomerOrder["Customer Order (3263)"] -->|ALLOCATED_TO| ProductionOrder
    CustomerOrder -->|PURCHASED_BY| Customer["Customer (7000)"]
    CustomerOrder -->|SERVICED_BY| Dealer["Dealership (50)"]
    
    Lot["Part Lot (364)"] -->|BATCH_OF| Part
    Lot -->|USED_AT| Plant
    
    Vehicle["Finished Vehicle (5348)"] -->|BUILT_FROM| ProductionOrder
    Vehicle -->|STOCKED_AT| Dealer
    Vehicle -->|OWNED_BY| Customer

    classDef core fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef comp fill:#065f46,stroke:#10b981,stroke-width:2px,color:#fff;
    classDef cust fill:#701a75,stroke:#d946ef,stroke-width:2px,color:#fff;

    class Plant,Model,ProductionOrder core;
    class Part,Supplier,Shipment,Lot comp;
    class CustomerOrder,Customer,Dealer,Vehicle cust;
```

---

## 2. Event Traversal Paths (Ground Truth Blast Radius)

The multi-agent system dynamically traverses the graph at runtime to resolve the exact blast radius of every operational disruption:

### 1. Supplier Delay Path
$$\text{Shipment} \xrightarrow{\text{carries}} \text{Part} \xrightarrow{\text{BOM}} \text{Model} \xrightarrow{\text{schedules}} \text{ProductionOrder} \xrightarrow{\text{allocates}} \text{CustomerOrder} \xrightarrow{\text{notifies}} \text{Dealer / Customer}$$
* **Evaluation Evidence:**
  `Shipment(SH-0182) → Part(CAM-360) → Model(VOYAGER) [BOM] → ProductionOrder(PO-0316) [2027-03-15] → CustomerOrder(CO-01756) → Dealer(D07) / Customer(C4130)`

---

### 2. Plant Outage Path
$$\text{Plant} \xrightarrow{\text{halts}} \text{ProductionOrder} \xrightarrow{\text{reschedules}} \text{Available Slot / Transfer Plant} \xrightarrow{\text{affects}} \text{CustomerOrder} \to \text{Dealer / Customer}$$
* **Evaluation Evidence:**
  `Plant(P_KY) → ProductionOrder(PO-0139) [PIONEER on 2027-03-16] → CustomerOrder(CO-00717) → Dealer(D42) / Customer(C5240)`

---

### 3. Quality Hold Path
$$\text{Lot} \xrightarrow{\text{defective part}} \text{ProductionOrder} \xrightarrow{\text{manufactured}} \text{FinishedVehicle} \xrightarrow{\text{split}} \begin{cases} \text{in\_stock} \to \text{Dealer (Stop-Sale)} \\ \text{sold} \to \text{Customer (Recall Alert)} \end{cases}$$
* **Evaluation Evidence:**
  * Unsold: `Lot(LOT-0191) → ProductionOrder(PO-0289) → Vehicle(AUR0003180) [in_stock] → Dealer(D15)`
  * Sold: `Lot(LOT-0191) → ProductionOrder(PO-0289) → Vehicle(AUR0003174) [sold] → Customer(C0310)`

---

## 3. Scale and Topology Metrics

* **Total Nodes:** 16,955
  * Plants: 6
  * Models: 6
  * Parts: 20
  * Suppliers: 18
  * Inbound Shipments: 364
  * Part Lots: 364
  * Production Orders: 540
  * Customer Orders: 3,263
  * Finished Vehicles: 5,348
  * Dealerships: 50
  * Customers: 7,000
* **Graph Traversal Latency:** $< 0.005$ seconds per event query.
