# Shop-floor PLC feed

Mill production in Easy-Books (weaving looms, spinning frames, processing lines,
weighbridges) is entered on green forms today. This feed lets a **shop-floor
gateway** push those readings so machine-wise production is recorded
automatically.

Easy-Books **does not poll Modbus, OPC-UA, Siemens S7, or MQTT**. Those
protocols stay on the mill OT network. A gateway (Node-RED, Kepware, Ignition,
or a small agent) reads PLC tags and POSTs JSON to `/api/plc/ingest`.

## Why push, not poll

| Constraint | Consequence |
|---|---|
| PLCs live on OT LANs (often no internet route) | A SaaS backend cannot open `:502` / `:4840` |
| Cloud host (Vercel / Neon) has no mill VPN | Inbound HTTPS from the mill is the only reliable path |
| Bank feeds / biometric attendance already use this shape | API key + idempotent upsert, not a new OT stack |

## What auto-records vs what waits

| Event type | Default | Writes | GL |
|---|---|---|---|
| `weaving.production` | auto-apply | `WvProduction` (source=`plc`) | No (weaving is memo) |
| `weighbridge.weigh` | auto-apply | ticket first/second weigh | No |
| `spinning.cone_output` | auto-apply | cone output **draft** | No until Approve |
| `spinning.stage` | **queue** | stage + GL **on Apply** | Yes — supervisor confirms |
| `textile.stage` | **queue** | PPC stage on Apply | No extra GL on the stage itself |
| `manufacturing.output` | log only | review queue | Completing a PO still happens on the floor |

A device can override `auto_apply`. Spinning stages should stay queued unless
the mill trusts the tag map.

## Gateway payload

```http
POST /api/plc/ingest
Authorization: Bearer eb_live_…
Content-Type: application/json

{
  "idempotency_key": "L-01-2026-10-15T08:00:00Z",
  "machine_code": "L-01",
  "event_type": "weaving.production",
  "occurred_at": "2026-10-15T08:00:00Z",
  "readings": {
    "grey_meters": 2200,
    "warp_yarn_kg": 120,
    "weft_yarn_kg": 80
  }
}
```

`idempotency_key` is unique per tenant. Retries return the original event
(`replayed: true`) and never double-count meters.

Map mill machines on **PLC Feed** (`/shop-floor`): code `L-01` → event type
`weaving.production` + binding `{ "contract_id": 12 }`. Readings override
binding. Create the API key under **Settings → API keys** (authenticates as
that user).

## Tag → field map (typical)

**Weaving loom:** pick counter / cloth meters → `grey_meters`; optional warp/weft
kg from beam scales; shift from the time-of-day or HMI.

**Spinning frame:** doff kg → `output_kg`; feed kg → `input_kg`; waste = input −
output. Bind `spin_lot_id` (or send `lot_number`) and `stage`
(`opening`…`winding`).

**Processing line:** meter counter → `input_mtr` / `output_mtr`. Bind
`production_order_id` + `process_code`.

**Weighbridge:** head 1 / head 2 → `gross_kg` + `tare_kg` (or sequential
`kind=gross|tare` + `kg`) with `vehicle_no`.

## What this is not

- Not a SCADA historian (no analog trend store)
- Not a MES finite scheduler
- Not live PLC ladder in the browser
- Not an installer that walks the mill network looking for devices

Those belong in the gateway. Easy-Books stores the **accounting/ops document**
the mill already types by hand.
