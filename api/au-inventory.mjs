const IDS = ["1629484", "1629486"];
const API = "https://api.steampowered.com/IPhysicalGoodsService/CheckInventoryAvailableByPackage/v1/";

async function getEgressCountry() {
  const r = await fetch("https://www.cloudflare.com/cdn-cgi/trace", {
    headers: { "User-Agent": "SteamFrameAUStockWatcher/1.0" },
    signal: AbortSignal.timeout(10000),
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`Egress verification HTTP ${r.status}`);
  const m = (await r.text()).match(/^loc=([A-Z]{2})\s*$/m);
  if (!m) throw new Error("Egress location could not be verified");
  return m[1];
}

async function check(packageid) {
  const u = new URL(API);
  u.searchParams.set("origin", "https://store.steampowered.com");
  u.searchParams.set("country_code", "AU");
  u.searchParams.set("packageid", packageid);
  const r = await fetch(u, {
    headers: { "User-Agent": "SteamFrameAUStockWatcher/1.0", Accept: "application/json" },
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (!r.ok) throw new Error(`Steam HTTP ${r.status} on package ${packageid}`);
  const j = await r.json();
  const value = j?.response?.inventory_available;
  if (typeof value !== "boolean") throw new Error(`No boolean inventory value for ${packageid}`);
  return value;
}

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });
  const region = process.env.VERCEL_REGION || "unknown";
  if (region !== "syd1") return res.status(503).json({ error: "Not running in Sydney", region });
  try {
    const egress_country = await getEgressCountry();
    if (egress_country !== "AU") {
      return res.status(503).json({ error: "Outbound IP is not Australian", region, egress_country });
    }
    const result = await Promise.all(IDS.map(check));
    return res.status(200).json({
      region, egress_country, country_code: "AU",
      source: "Steam physical goods inventory API (not storefront Add to Cart button)",
      checked_at: new Date().toISOString(),
      models: Object.fromEntries(IDS.map((id, i) => [id, result[i]])),
    });
  } catch (e) {
    return res.status(502).json({ error: String(e?.message || e), region });
  }
}
