// src/pages/I18nPage.jsx
import { useState, useRef } from "react";
import {
  useLanguages,
  useCountries,
  useCurrencies,
  useTimezones,
  useTranslations,
  useTranslationKeys,
  useMissingTranslations,
} from "../hooks/useI18n";
import PageEndpointPanel from '../components/common/PageEndpointPanel';

// ─── ICONS ────────────────────────────────────────────────────────────────
const SVG = ({ d, size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {d.split("||").map((path, i) => <path key={i} d={path} />)}
  </svg>
);
const icons = {
  globe:    "M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2z||M2 12h20||M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z",
  flag:     "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z||M4 22v-7",
  coin:     "M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2z||M12 6v2||M12 16v2||M8.5 9.5l1.5 1.5-1.5 1.5||M15.5 9.5l-1.5 1.5 1.5 1.5",
  clock:    "M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2z||M12 6v6l4 2",
  city:     "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z||M9 22V12h6v10",
  key:      "M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4",
  translate:"M5 4h14||M9 4v4||M4 8h8||M7.5 8c0 3.5 2 6.5 4.5 8||M17 8c0 3.5-2 6.5-4.5 8||M12 20c0-4 2-7 5-8||M12 20c0-4-2-7-5-8",
  alert:    "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z||M12 9v4||M12 17h.01",
  check:    "M20 6L9 17l-5-5",
  plus:     "M12 5v14||M5 12h14",
  edit:     "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7||M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  trash:    "M3 6h18||M19 6l-1 14H6L5 6||M8 6V4h8v2",
  upload:   "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4||M17 8l-5-5-5 5||M12 3v12",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4||M7 10l5 5 5-5||M12 15V3",
  refresh:  "M23 4v6h-6||M1 20v-6h6||M3.51 9a9 9 0 0 1 14.85-3.36L23 10||M1 14l4.64 4.36A9 9 0 0 0 20.49 15",
  star:     "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
};
const Icon = ({ name, size = 15 }) => <SVG d={icons[name] || icons.globe} size={size} />;

// ─── SHARED STYLES ────────────────────────────────────────────────────────
const input = {
  width: "100%", background: "rgba(255,255,255,0.05)",
  border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8,
  padding: "9px 12px", color: "#f2f2f7", fontSize: 13, outline: "none",
  boxSizing: "border-box", fontFamily: "inherit",
};
const badge = (color, bg) => ({
  color, background: bg, padding: "2px 9px", borderRadius: 20,
  fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
  display: "inline-flex", alignItems: "center",
});

const Btn = ({ children, onClick, variant = "ghost", size = "sm", disabled }) => {
  const styles = {
    primary: { background: "#0a84ff", color: "#fff" },
    success: { background: "rgba(48,209,88,0.15)", color: "#30d158", border: "1px solid rgba(48,209,88,0.3)" },
    danger:  { background: "rgba(255,45,85,0.1)",  color: "#ff2d55",  border: "1px solid rgba(255,45,85,0.2)" },
    ghost:   { background: "rgba(255,255,255,0.06)", color: "#8e8e93" },
  };
  return (
    <button onClick={onClick} disabled={disabled} style={{
      ...styles[variant], border: "none", borderRadius: 7,
      padding: size === "sm" ? "6px 14px" : "9px 20px",
      fontSize: size === "sm" ? 12 : 13, fontWeight: 600,
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1,
      display: "inline-flex", alignItems: "center", gap: 6,
      transition: "opacity 0.15s",
    }}>
      {children}
    </button>
  );
};

const Label = ({ children }) => (
  <label style={{ display: "block", color: "#8e8e93", fontSize: 11, fontWeight: 600,
    letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 6 }}>
    {children}
  </label>
);

const FormField = ({ label, children }) => (
  <div style={{ marginBottom: 14 }}>
    <Label>{label}</Label>
    {children}
  </div>
);

const SectionTitle = ({ children, count }) => (
  <div style={{ marginBottom: 18 }}>
    <h3 style={{ color: "#f2f2f7", fontWeight: 700, fontSize: 15, margin: 0 }}>
      {children}
      {count !== undefined && (
        <span style={{ color: "#636366", fontWeight: 400, fontSize: 12, marginLeft: 8 }}>
          ({count})
        </span>
      )}
    </h3>
  </div>
);

const EmptyState = ({ icon, text }) => (
  <div style={{ padding: "48px 0", textAlign: "center", color: "#48484a" }}>
    <div style={{ fontSize: 28, marginBottom: 10 }}>{icon}</div>
    <div style={{ fontSize: 13 }}>{text}</div>
  </div>
);

const Loader = () => (
  <div style={{ padding: "48px 0", textAlign: "center", color: "#636366", fontSize: 13 }}>
    Loading...
  </div>
);

// Table
const TableHead = ({ cols }) => (
  <div style={{ display: "grid", gridTemplateColumns: cols, padding: "10px 16px",
    borderBottom: "1px solid rgba(255,255,255,0.06)", color: "#48484a",
    fontSize: 11, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
  </div>
);

const TableWrap = ({ children }) => (
  <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 12, overflow: "hidden" }}>
    {children}
  </div>
);

const Row = ({ children, cols, onClick }) => (
  <div style={{ display: "grid", gridTemplateColumns: cols,
    padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)",
    alignItems: "center", fontSize: 13, color: "#8e8e93", cursor: onClick ? "pointer" : "default" }}
    onClick={onClick}>
    {children}
  </div>
);

// ─── INLINE EDIT ROW ──────────────────────────────────────────────────────
const EditableRow = ({ item, fields, cols, onSave, onDelete, renderExtra }) => {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(item);

  const handleSave = async () => {
    await onSave(item.id, form);
    setEditing(false);
  };

  if (editing) {
    return (
      <div style={{ padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)",
        background: "rgba(10,132,255,0.04)" }}>
        <div style={{ display: "grid", gridTemplateColumns: cols, gap: 8, alignItems: "center" }}>
          {fields.map(f => (
            <input key={f.key} value={form[f.key] || ""} placeholder={f.label}
              onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
              style={{ ...input, padding: "6px 10px", fontSize: 12 }} />
          ))}
          <div style={{ display: "flex", gap: 6 }}>
            <Btn variant="success" onClick={handleSave}><Icon name="check" size={12} /></Btn>
            <Btn variant="ghost" onClick={() => setEditing(false)}>✕</Btn>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: cols,
      padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)",
      alignItems: "center", fontSize: 13, color: "#8e8e93" }}>
      {fields.map(f => (
        <span key={f.key} style={{ color: f.primary ? "#f2f2f7" : "#8e8e93" }}>
          {item[f.key] || "—"}
        </span>
      ))}
      {renderExtra && renderExtra(item)}
      <div style={{ display: "flex", gap: 4 }}>
        <button onClick={() => setEditing(true)} style={{ background: "none", border: "none",
          color: "#636366", cursor: "pointer", padding: "3px 6px", borderRadius: 5 }}>
          <Icon name="edit" size={13} />
        </button>
        <button onClick={() => onDelete(item.id)} style={{ background: "none", border: "none",
          color: "#ff2d55", cursor: "pointer", padding: "3px 6px", borderRadius: 5 }}>
          <Icon name="trash" size={13} />
        </button>
      </div>
    </div>
  );
};

// ─── TAB: LANGUAGES ───────────────────────────────────────────────────────
const LanguagesTab = () => {
  const { languages, loading, saving, createLanguage, updateLanguage, deleteLanguage, setDefault } = useLanguages();
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", name_native: "", flag_emoji: "", is_rtl: false });

  const handleAdd = async () => {
    await createLanguage(form);
    setShowAdd(false);
    setForm({ code: "", name: "", name_native: "", flag_emoji: "", is_rtl: false });
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <SectionTitle count={languages.length}>Languages</SectionTitle>
        <Btn variant="primary" onClick={() => setShowAdd(!showAdd)}>
          <Icon name="plus" size={13} /> Add Language
        </Btn>
      </div>

      {showAdd && (
        <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 12, padding: 18, marginBottom: 18 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 60px auto", gap: 10, alignItems: "flex-end" }}>
            {[["Code (e.g. en)", "code"], ["Name", "name"], ["Native Name", "name_native"], ["Flag", "flag_emoji"]].map(([label, key]) => (
              <FormField key={key} label={label}>
                <input value={form[key]} onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))} style={input} />
              </FormField>
            ))}
            <FormField label="RTL">
              <div style={{ display: "flex", alignItems: "center", height: 38 }}>
                <input type="checkbox" checked={form.is_rtl}
                  onChange={e => setForm(p => ({ ...p, is_rtl: e.target.checked }))}
                  style={{ width: 16, height: 16, cursor: "pointer" }} />
              </div>
            </FormField>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <Btn variant="success" onClick={handleAdd} disabled={saving || !form.code}>
              {saving ? "Adding..." : "Add"}
            </Btn>
            <Btn variant="ghost" onClick={() => setShowAdd(false)}>Cancel</Btn>
          </div>
        </div>
      )}

      {loading ? <Loader /> : languages.length === 0 ? <EmptyState icon="🌐" text="No languages configured" /> : (
        <TableWrap>
          <div style={{ display: "grid", gridTemplateColumns: "80px 160px 160px 60px 80px 80px auto",
            padding: "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)",
            color: "#48484a", fontSize: 11, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
            {["Code", "Name", "Native", "Flag", "RTL", "Status", ""].map(h => <span key={h}>{h}</span>)}
          </div>
          {languages.map(lang => (
            <div key={lang.id} style={{ display: "grid",
              gridTemplateColumns: "80px 160px 160px 60px 80px 80px auto",
              padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)",
              alignItems: "center", fontSize: 13 }}>
              <span style={{ color: "#0a84ff", fontFamily: "'Courier New', monospace", fontWeight: 700 }}>
                {lang.code}
              </span>
              <span style={{ color: "#f2f2f7" }}>{lang.name}</span>
              <span style={{ color: "#8e8e93" }}>{lang.name_native || "—"}</span>
              <span style={{ fontSize: 20 }}>{lang.flag_emoji || "—"}</span>
              <span style={{ color: lang.is_rtl ? "#ffd60a" : "#48484a", fontSize: 12 }}>
                {lang.is_rtl ? "RTL" : "LTR"}
              </span>
              <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                <span style={lang.is_active
                  ? badge("#30d158", "rgba(48,209,88,0.12)")
                  : badge("#636366", "rgba(99,99,102,0.12)")}>
                  {lang.is_active ? "ACTIVE" : "OFF"}
                </span>
                {lang.is_default && (
                  <span style={badge("#ffd60a", "rgba(255,214,10,0.12)")}>DEFAULT</span>
                )}
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                {!lang.is_default && (
                  <button onClick={() => setDefault(lang.id)} title="Set as default"
                    style={{ background: "none", border: "none", color: "#636366", cursor: "pointer", padding: "3px 6px" }}>
                    <Icon name="star" size={13} />
                  </button>
                )}
                <button onClick={() => updateLanguage(lang.id, { is_active: !lang.is_active })}
                  style={{ background: "none", border: "none",
                    color: lang.is_active ? "#ffd60a" : "#30d158", cursor: "pointer", padding: "3px 6px" }}>
                  <Icon name={lang.is_active ? "flag" : "check"} size={13} />
                </button>
                <button onClick={() => deleteLanguage(lang.id)}
                  style={{ background: "none", border: "none", color: "#ff2d55", cursor: "pointer", padding: "3px 6px" }}>
                  <Icon name="trash" size={13} />
                </button>
              </div>
            </div>
          ))}
        </TableWrap>
      )}
    </div>
  );
};

// ─── TAB: COUNTRIES ───────────────────────────────────────────────────────
const CountriesTab = () => {
  const { countries, loading, saving, createCountry, updateCountry, deleteCountry } = useCountries();
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", phone_code: "", flag_emoji: "" });
  const [search, setSearch] = useState("");

  const filtered = countries.filter(c =>
    !search || c.name?.toLowerCase().includes(search.toLowerCase()) || c.code?.toLowerCase().includes(search.toLowerCase())
  );

  const handleAdd = async () => {
    await createCountry(form);
    setShowAdd(false);
    setForm({ code: "", name: "", phone_code: "", flag_emoji: "" });
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <SectionTitle count={countries.length}>Countries</SectionTitle>
        <div style={{ display: "flex", gap: 10 }}>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search..." style={{ ...input, width: 200, padding: "7px 12px" }} />
          <Btn variant="primary" onClick={() => setShowAdd(!showAdd)}>
            <Icon name="plus" size={13} /> Add
          </Btn>
        </div>
      </div>

      {showAdd && (
        <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 12, padding: 18, marginBottom: 18 }}>
          <div style={{ display: "grid", gridTemplateColumns: "80px 1fr 120px 60px", gap: 10, alignItems: "flex-end" }}>
            {[["Code (2)", "code"], ["Country Name", "name"], ["Phone Code", "phone_code"], ["Flag", "flag_emoji"]].map(([label, key]) => (
              <FormField key={key} label={label}>
                <input value={form[key]} onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))} style={input} />
              </FormField>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <Btn variant="success" onClick={handleAdd} disabled={saving || !form.code}>
              {saving ? "Adding..." : "Add Country"}
            </Btn>
            <Btn variant="ghost" onClick={() => setShowAdd(false)}>Cancel</Btn>
          </div>
        </div>
      )}

      {loading ? <Loader /> : (
        <TableWrap>
          <div style={{ display: "grid", gridTemplateColumns: "60px 50px 200px 120px 80px 80px",
            padding: "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)",
            color: "#48484a", fontSize: 11, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
            {["Code", "Flag", "Name", "Phone", "Status", "Actions"].map(h => <span key={h}>{h}</span>)}
          </div>
          {filtered.slice(0, 50).map(c => (
            <div key={c.id} style={{ display: "grid", gridTemplateColumns: "60px 50px 200px 120px 80px 80px",
              padding: "11px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)", alignItems: "center" }}>
              <span style={{ color: "#0a84ff", fontFamily: "'Courier New', monospace", fontWeight: 700, fontSize: 12 }}>
                {c.code}
              </span>
              <span style={{ fontSize: 20 }}>{c.flag_emoji || "🏳️"}</span>
              <span style={{ color: "#f2f2f7", fontSize: 13 }}>{c.name}</span>
              <span style={{ color: "#8e8e93", fontSize: 12, fontFamily: "'Courier New', monospace" }}>{c.phone_code}</span>
              <span style={c.is_active ? badge("#30d158", "rgba(48,209,88,0.12)") : badge("#636366", "rgba(99,99,102,0.12)")}>
                {c.is_active ? "ACTIVE" : "OFF"}
              </span>
              <div style={{ display: "flex", gap: 4 }}>
                <button onClick={() => updateCountry(c.id, { is_active: !c.is_active })}
                  style={{ background: "none", border: "none", color: "#636366", cursor: "pointer", padding: "3px 6px" }}>
                  <Icon name="edit" size={13} />
                </button>
                <button onClick={() => deleteCountry(c.id)}
                  style={{ background: "none", border: "none", color: "#ff2d55", cursor: "pointer", padding: "3px 6px" }}>
                  <Icon name="trash" size={13} />
                </button>
              </div>
            </div>
          ))}
          {filtered.length > 50 && (
            <div style={{ padding: "12px 16px", color: "#48484a", fontSize: 12, textAlign: "center" }}>
              Showing 50 of {filtered.length} — use search to filter
            </div>
          )}
        </TableWrap>
      )}
    </div>
  );
};

// ─── TAB: CURRENCIES ──────────────────────────────────────────────────────
const CurrenciesTab = () => {
  const { currencies, loading, saving, createCurrency, updateCurrency, deleteCurrency, setDefault, updateRate, staleRateCurrencies } = useCurrencies();
  const [showAdd, setShowAdd] = useState(false);
  const [editRate, setEditRate] = useState(null);
  const [rateValue, setRateValue] = useState("");
  const [form, setForm] = useState({ code: "", name: "", symbol: "", decimal_digits: 2, exchange_rate: 1 });

  const handleAdd = async () => {
    await createCurrency(form);
    setShowAdd(false);
    setForm({ code: "", name: "", symbol: "", decimal_digits: 2, exchange_rate: 1 });
  };

  const handleRateSave = async (id) => {
    await updateRate(id, parseFloat(rateValue));
    setEditRate(null);
  };

  return (
    <div>
      {staleRateCurrencies.length > 0 && (
        <div style={{ background: "rgba(255,214,10,0.08)", border: "1px solid rgba(255,214,10,0.2)",
          borderRadius: 10, padding: "10px 16px", marginBottom: 18, display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "#ffd60a" }}><Icon name="alert" size={14} /></span>
          <span style={{ color: "#ffd60a", fontSize: 12 }}>
            {staleRateCurrencies.length} currencies have stale exchange rates (older than 24h)
          </span>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <SectionTitle count={currencies.length}>Currencies</SectionTitle>
        <Btn variant="primary" onClick={() => setShowAdd(!showAdd)}>
          <Icon name="plus" size={13} /> Add Currency
        </Btn>
      </div>

      {showAdd && (
        <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 12, padding: 18, marginBottom: 18 }}>
          <div style={{ display: "grid", gridTemplateColumns: "80px 1fr 80px 80px 120px", gap: 10, alignItems: "flex-end" }}>
            {[["Code (3)", "code"], ["Name", "name"], ["Symbol", "symbol"], ["Decimals", "decimal_digits"], ["Exchange Rate", "exchange_rate"]].map(([label, key]) => (
              <FormField key={key} label={label}>
                <input type={["decimal_digits","exchange_rate"].includes(key) ? "number" : "text"}
                  value={form[key]} onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))} style={input} />
              </FormField>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <Btn variant="success" onClick={handleAdd} disabled={saving || !form.code}>
              {saving ? "Adding..." : "Add Currency"}
            </Btn>
            <Btn variant="ghost" onClick={() => setShowAdd(false)}>Cancel</Btn>
          </div>
        </div>
      )}

      {loading ? <Loader /> : currencies.length === 0 ? <EmptyState icon="💰" text="No currencies configured" /> : (
        <TableWrap>
          <div style={{ display: "grid", gridTemplateColumns: "80px 60px 160px 80px 140px 80px auto",
            padding: "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)",
            color: "#48484a", fontSize: 11, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
            {["Code","Symbol","Name","Decimals","Exchange Rate","Status",""].map(h => <span key={h}>{h}</span>)}
          </div>
          {currencies.map(c => (
            <div key={c.id} style={{ display: "grid", gridTemplateColumns: "80px 60px 160px 80px 140px 80px auto",
              padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)", alignItems: "center" }}>
              <span style={{ color: "#0a84ff", fontFamily: "'Courier New', monospace", fontWeight: 700 }}>{c.code}</span>
              <span style={{ color: "#ffd60a", fontSize: 16 }}>{c.symbol}</span>
              <span style={{ color: "#f2f2f7", fontSize: 13 }}>{c.name}</span>
              <span style={{ color: "#8e8e93", fontSize: 12 }}>{c.decimal_digits}</span>
              <div>
                {editRate === c.id ? (
                  <div style={{ display: "flex", gap: 4 }}>
                    <input type="number" value={rateValue} onChange={e => setRateValue(e.target.value)}
                      style={{ ...input, padding: "4px 8px", fontSize: 12, width: 90 }} />
                    <button onClick={() => handleRateSave(c.id)}
                      style={{ background: "#30d158", color: "#000", border: "none", borderRadius: 5, padding: "4px 8px", cursor: "pointer" }}>
                      ✓
                    </button>
                  </div>
                ) : (
                  <button onClick={() => { setEditRate(c.id); setRateValue(c.exchange_rate); }}
                    style={{ background: "none", border: "none", color: "#8e8e93",
                      cursor: "pointer", fontFamily: "'Courier New', monospace", fontSize: 12 }}>
                    {Number(c.exchange_rate).toFixed(4)} ✎
                  </button>
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                <span style={c.is_active ? badge("#30d158","rgba(48,209,88,0.12)") : badge("#636366","rgba(99,99,102,0.12)")}>
                  {c.is_active ? "ACTIVE" : "OFF"}
                </span>
                {c.is_default && <span style={badge("#ffd60a","rgba(255,214,10,0.12)")}>DEFAULT</span>}
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                {!c.is_default && (
                  <button onClick={() => setDefault(c.id)} title="Set default"
                    style={{ background: "none", border: "none", color: "#636366", cursor: "pointer", padding: "3px 6px" }}>
                    <Icon name="star" size={13} />
                  </button>
                )}
                <button onClick={() => deleteCurrency(c.id)}
                  style={{ background: "none", border: "none", color: "#ff2d55", cursor: "pointer", padding: "3px 6px" }}>
                  <Icon name="trash" size={13} />
                </button>
              </div>
            </div>
          ))}
        </TableWrap>
      )}
    </div>
  );
};

// ─── TAB: TRANSLATIONS ────────────────────────────────────────────────────
const TranslationsTab = () => {
  const [langFilter, setLangFilter] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [approvedFilter, setApprovedFilter] = useState("");
  const [search, setSearch] = useState("");

  const { translations, loading, saving, updateTranslation, approveTranslation, bulkApprove, pendingTranslations, setParams } = useTranslations(
    Object.fromEntries(Object.entries({ language: langFilter, is_approved: approvedFilter }).filter(([, v]) => v !== ""))
  );
  const { keys, categories } = useTranslationKeys();
  const { languages } = useLanguages({ is_active: true });

  const [selected, setSelected] = useState([]);
  const [editId, setEditId] = useState(null);
  const [editValue, setEditValue] = useState("");

  const filtered = translations.filter(t =>
    !search || t.key?.key?.toLowerCase().includes(search.toLowerCase()) || t.value?.toLowerCase().includes(search.toLowerCase())
  );

  const handleBulkApprove = async () => {
    await bulkApprove(selected);
    setSelected([]);
  };

  const handleSaveEdit = async (id) => {
    await updateTranslation(id, { value: editValue });
    setEditId(null);
  };

  return (
    <div>
      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 18, flexWrap: "wrap", alignItems: "center" }}>
        <select value={langFilter} onChange={e => setLangFilter(e.target.value)}
          style={{ ...input, width: 140, padding: "7px 10px" }}>
          <option value="">All Languages</option>
          {languages.map(l => <option key={l.id} value={l.id}>{l.flag_emoji} {l.name}</option>)}
        </select>
        <select value={approvedFilter} onChange={e => setApprovedFilter(e.target.value)}
          style={{ ...input, width: 150, padding: "7px 10px" }}>
          <option value="">All Status</option>
          <option value="true">Approved</option>
          <option value="false">Pending</option>
        </select>
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search key or value..." style={{ ...input, width: 220, padding: "7px 12px" }} />
        {pendingTranslations.length > 0 && (
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ color: "#ffd60a", fontSize: 12 }}>
              {pendingTranslations.length} pending
            </span>
            {selected.length > 0 && (
              <Btn variant="success" onClick={handleBulkApprove}>
                <Icon name="check" size={12} /> Approve {selected.length}
              </Btn>
            )}
          </div>
        )}
      </div>

      {loading ? <Loader /> : (
        <TableWrap>
          <div style={{ display: "grid", gridTemplateColumns: "32px 200px 120px 1fr 80px 100px",
            padding: "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)",
            color: "#48484a", fontSize: 11, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
            {["","Key","Language","Value","Source","Actions"].map(h => <span key={h}>{h}</span>)}
          </div>
          {filtered.slice(0, 60).map(t => (
            <div key={t.id} style={{ display: "grid", gridTemplateColumns: "32px 200px 120px 1fr 80px 100px",
              padding: "11px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)",
              alignItems: "center", background: !t.is_approved ? "rgba(255,214,10,0.02)" : "transparent" }}>
              <input type="checkbox" checked={selected.includes(t.id)}
                onChange={e => setSelected(prev => e.target.checked ? [...prev, t.id] : prev.filter(i => i !== t.id))}
                style={{ width: 14, height: 14, cursor: "pointer" }} />
              <span style={{ color: "#8e8e93", fontSize: 11, fontFamily: "'Courier New', monospace" }}>
                {t.key?.key?.slice(0, 30) || "—"}
              </span>
              <span style={{ color: "#0a84ff", fontSize: 12 }}>
                {t.language?.flag_emoji} {t.language?.code}
              </span>
              <div>
                {editId === t.id ? (
                  <div style={{ display: "flex", gap: 6 }}>
                    <input value={editValue} onChange={e => setEditValue(e.target.value)}
                      style={{ ...input, padding: "5px 10px", fontSize: 12 }} />
                    <button onClick={() => handleSaveEdit(t.id)}
                      style={{ background: "#30d158", color: "#000", border: "none", borderRadius: 5, padding: "5px 10px", cursor: "pointer", fontSize: 12 }}>
                      Save
                    </button>
                  </div>
                ) : (
                  <span style={{ color: "#f2f2f7", fontSize: 13 }}>
                    {t.value?.slice(0, 80)}{t.value?.length > 80 ? "..." : ""}
                  </span>
                )}
              </div>
              <span style={{ fontSize: 11, color: t.source === "auto" ? "#bf5af2" : "#636366" }}>
                {t.source || "manual"}
              </span>
              <div style={{ display: "flex", gap: 4 }}>
                {!t.is_approved && (
                  <button onClick={() => approveTranslation(t.id)} title="Approve"
                    style={{ background: "rgba(48,209,88,0.12)", color: "#30d158", border: "none",
                      borderRadius: 5, padding: "3px 7px", cursor: "pointer", fontSize: 11 }}>
                    ✓
                  </button>
                )}
                <button onClick={() => { setEditId(t.id); setEditValue(t.value); }}
                  style={{ background: "none", border: "none", color: "#636366", cursor: "pointer", padding: "3px 6px" }}>
                  <Icon name="edit" size={12} />
                </button>
              </div>
            </div>
          ))}
        </TableWrap>
      )}
    </div>
  );
};

// ─── TAB: MISSING ─────────────────────────────────────────────────────────
const MissingTab = () => {
  const { missing, stats, loading, resolve, bulkResolve, totalMissing } = useMissingTranslations();
  const [selected, setSelected] = useState([]);

  const groupedByLang = missing.reduce((acc, m) => {
    const lang = m.language?.code || "unknown";
    if (!acc[lang]) acc[lang] = [];
    acc[lang].push(m);
    return acc;
  }, {});

  return (
    <div>
      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 24 }}>
        {[
          { label: "Total Missing", value: totalMissing, color: "#ff2d55" },
          { label: "Languages Affected", value: Object.keys(groupedByLang).length, color: "#ffd60a" },
          { label: "Resolved Today", value: stats?.resolved_today || 0, color: "#30d158" },
        ].map(s => (
          <div key={s.label} style={{
            background: "rgba(255,255,255,0.03)", border: `1px solid rgba(255,255,255,0.07)`,
            borderRadius: 10, padding: "14px 18px", borderTop: `2px solid ${s.color}`,
          }}>
            <div style={{ color: s.color, fontSize: 26, fontWeight: 800, fontFamily: "'Courier New', monospace" }}>
              {s.value}
            </div>
            <div style={{ color: "#636366", fontSize: 11, marginTop: 3 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {selected.length > 0 && (
        <div style={{ marginBottom: 14, display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ color: "#8e8e93", fontSize: 12 }}>{selected.length} selected</span>
          <Btn variant="success" onClick={() => bulkResolve(selected)}>
            <Icon name="check" size={12} /> Resolve Selected
          </Btn>
          <Btn variant="ghost" onClick={() => setSelected([])}>Clear</Btn>
        </div>
      )}

      {loading ? <Loader /> : missing.length === 0 ? (
        <div style={{ padding: "60px 0", textAlign: "center" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>✅</div>
          <div style={{ color: "#30d158", fontWeight: 600 }}>All translations accounted for!</div>
        </div>
      ) : (
        <TableWrap>
          <div style={{ display: "grid", gridTemplateColumns: "32px 240px 100px 200px 80px 100px",
            padding: "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)",
            color: "#48484a", fontSize: 11, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
            {["","Key","Language","Path","Date","Actions"].map(h => <span key={h}>{h}</span>)}
          </div>
          {missing.map(m => (
            <div key={m.id} style={{ display: "grid", gridTemplateColumns: "32px 240px 100px 200px 80px 100px",
              padding: "11px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)", alignItems: "center" }}>
              <input type="checkbox" checked={selected.includes(m.id)}
                onChange={e => setSelected(prev => e.target.checked ? [...prev, m.id] : prev.filter(i => i !== m.id))}
                style={{ width: 14, height: 14, cursor: "pointer" }} />
              <span style={{ color: "#ff2d55", fontFamily: "'Courier New', monospace", fontSize: 12 }}>
                {m.key?.slice(0, 40)}
              </span>
              <span style={{ color: "#0a84ff", fontSize: 12 }}>
                {m.language?.flag_emoji} {m.language?.code}
              </span>
              <span style={{ color: "#636366", fontSize: 11 }}>
                {m.request_path?.slice(0, 40) || "—"}
              </span>
              <span style={{ color: "#48484a", fontSize: 11 }}>
                {m.created_at ? new Date(m.created_at).toLocaleDateString() : "—"}
              </span>
              <Btn variant="success" onClick={() => resolve(m.id)}>
                <Icon name="check" size={11} /> Resolve
              </Btn>
            </div>
          ))}
        </TableWrap>
      )}
    </div>
  );
};

// ─── MAIN PAGE ────────────────────────────────────────────────────────────
const TABS = [
  { id: "languages",    label: "Languages",    icon: "globe" },
  { id: "countries",    label: "Countries",    icon: "flag" },
  { id: "currencies",   label: "Currencies",   icon: "coin" },
  { id: "timezones",    label: "Timezones",    icon: "clock" },
  { id: "translations", label: "Translations", icon: "translate" },
  { id: "missing",      label: "Missing",      icon: "alert" },
];

export default function I18nPage() {
  const [activeTab, setActiveTab] = useState("languages");
  const { languages } = useLanguages({ is_active: true });
  const { missing } = useMissingTranslations();
  const { staleRateCurrencies } = useCurrencies();

  const alerts = missing.filter(m => !m.resolved).length + staleRateCurrencies.length;

  return (
    <div style={{
      minHeight: "100vh",
      background: "#000",
      color: "#f2f2f7",
      fontFamily: "'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif",
      padding: 24,
    }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: "linear-gradient(135deg, #bf5af2, #0a84ff)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Icon name="globe" size={18} />
              <PageEndpointPanel pageKey="Localization" title="Localization Endpoints" />
          </div>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: "#f2f2f7", letterSpacing: "-0.02em", margin: 0 }}>
              Localization & i18n
            </h1>
            <p style={{ color: "#636366", fontSize: 12, margin: 0 }}>
              Languages · Countries · Currencies · Translations
            </p>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 14 }}>
            <div style={{ textAlign: "right" }}>
              <div style={{ color: "#f2f2f7", fontWeight: 700, fontFamily: "'Courier New', monospace", fontSize: 18 }}>
                {languages.length}
              </div>
              <div style={{ color: "#636366", fontSize: 11 }}>Languages</div>
            </div>
            {alerts > 0 && (
              <div style={{
                background: "rgba(255,45,85,0.12)", border: "1px solid rgba(255,45,85,0.25)",
                borderRadius: 8, padding: "6px 12px",
                display: "flex", alignItems: "center", gap: 6,
                color: "#ff2d55", fontSize: 12, fontWeight: 600,
              }}>
                <Icon name="alert" size={13} />
                {alerts} issue{alerts !== 1 ? "s" : ""}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 2, marginBottom: 24,
        background: "rgba(255,255,255,0.04)", borderRadius: 10, padding: 4 }}>
        {TABS.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 7,
              padding: "8px 12px", borderRadius: 8, border: "none", cursor: "pointer",
              fontSize: 12, fontWeight: 600, transition: "all 0.15s",
              background: activeTab === tab.id ? "#0a84ff" : "transparent",
              color: activeTab === tab.id ? "#fff" : "#636366",
              position: "relative",
            }}>
            <Icon name={tab.icon} size={13} />
            {tab.label}
            {tab.id === "missing" && missing.length > 0 && (
              <span style={{
                position: "absolute", top: 4, right: 4,
                background: "#ff2d55", color: "#fff", borderRadius: 10,
                padding: "1px 5px", fontSize: 9, fontWeight: 800,
                minWidth: 16, textAlign: "center",
              }}>
                {missing.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === "languages"    && <LanguagesTab />}
      {activeTab === "countries"    && <CountriesTab />}
      {activeTab === "currencies"   && <CurrenciesTab />}
      {activeTab === "timezones"    && <TimezonesTab />}
      {activeTab === "translations" && <TranslationsTab />}
      {activeTab === "missing"      && <MissingTab />}
    </div>
  );
}

// ─── TAB: TIMEZONES ───────────────────────────────────────────────────────
const TimezonesTab = () => {
  const { timezones, loading } = useTimezones({ is_active: true });
  const [search, setSearch] = useState("");

  const filtered = timezones.filter(t =>
    !search || t.name?.toLowerCase().includes(search.toLowerCase()) ||
    t.code?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <SectionTitle count={timezones.length}>Timezones</SectionTitle>
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search timezone..." style={{ ...input, width: 220, padding: "7px 12px" }} />
      </div>

      {loading ? <Loader /> : (
        <TableWrap>
          <div style={{ display: "grid", gridTemplateColumns: "200px 80px 80px 1fr 80px",
            padding: "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.06)",
            color: "#48484a", fontSize: 11, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
            {["Name","Code","Offset","UTC Offset (sec)","DST"].map(h => <span key={h}>{h}</span>)}
          </div>
          {filtered.slice(0, 50).map(tz => (
            <div key={tz.id} style={{ display: "grid", gridTemplateColumns: "200px 80px 80px 1fr 80px",
              padding: "11px 16px", borderBottom: "1px solid rgba(255,255,255,0.04)", alignItems: "center" }}>
              <span style={{ color: "#f2f2f7", fontSize: 13 }}>{tz.name}</span>
              <span style={{ color: "#0a84ff", fontFamily: "'Courier New', monospace", fontSize: 12 }}>{tz.code}</span>
              <span style={{ color: "#30d158", fontFamily: "'Courier New', monospace", fontSize: 12 }}>{tz.offset || "—"}</span>
              <span style={{ color: "#636366", fontSize: 11 }}>{tz.offset_seconds?.toLocaleString()}</span>
              <span style={{ color: tz.is_dst ? "#ffd60a" : "#48484a", fontSize: 12 }}>
                {tz.is_dst ? "DST" : "—"}
              </span>
            </div>
          ))}
        </TableWrap>
      )}
    </div>
  );
};