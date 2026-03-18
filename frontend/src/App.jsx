import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

import {
  LayoutDashboard,
  Users,
  Phone,
  Activity,
  Settings
} from "lucide-react";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer
} from "recharts";

const API = import.meta.env.VITE_API_URL || "https://ai-insurance-agent-deploy-2.onrender.com";

export default function App() {

  const [page, setPage] = useState("dashboard");
  const [customers, setCustomers] = useState([]);
  const [logs, setLogs] = useState([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [showModal, setShowModal] = useState(false);

  const fetchData = async () => {
    try {
      const c = await axios.get(`${API}/customers`);
      const l = await axios.get(`${API}/call-logs`);
      setCustomers(c.data);
      setLogs(l.data);
    } catch (err) {
      console.log(err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const makeCall = async (id) => {
    await axios.post(`${API}/make-call/${id}`);
    fetchData();
  };

  const runAI = async () => {
    await axios.post(`${API}/trigger-auto-call`);
    alert("Auto call triggered!");
  };

  const addCustomer = async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    await axios.post(`${API}/add-customer`, null, {
      params: {
        name: form.get("name"),
        phone: form.get("phone"),
        policy: form.get("policy"),
        amount: form.get("amount"),
        days_due: form.get("days")
      }
    });
    setShowModal(false);
    fetchData();
  };

  // ── Helpers ──────────────────────────────────────────────────────────────

  const getCustomerName = (customer_id) => {
    const c = customers.find(c => c.id === customer_id);
    return c ? c.name : `ID: ${customer_id}`;
  };

  const getCustomerPhone = (customer_id) => {
    const c = customers.find(c => c.id === customer_id);
    return c ? c.phone : "—";
  };

  const formatTime = (raw) => {
    if (!raw) return "—";
    try {
      const d = new Date(raw);
      return d.toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
    } catch {
      return raw;
    }
  };

  const getStatus = (c) => c.payment_status || c.status || "—";
  const getPolicy = (c) => c.policy_number || c.policy || "—";

  // ── Chart data ────────────────────────────────────────────────────────────

  const chartData = [
    { name: "Paid", value: customers.filter(c => getStatus(c) === "paid").length },
    { name: "Pending", value: customers.filter(c => getStatus(c) === "pending").length }
  ];

  const filtered = customers.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  // ── UI ────────────────────────────────────────────────────────────────────

  return (
    <div className="app">

      {/* SIDEBAR */}
      <div className="sidebar">
        <h2 className="logo">AI Insurance</h2>
        <button className="navBtn" onClick={() => setPage("dashboard")}>
          <LayoutDashboard size={18} /> Dashboard
        </button>
        <button className="navBtn" onClick={() => setPage("customers")}>
          <Users size={18} /> Customers
        </button>
        <button className="navBtn" onClick={() => setPage("logs")}>
          <Phone size={18} /> Call Logs
        </button>
        <button className="navBtn" onClick={() => setPage("analytics")}>
          <Activity size={18} /> Analytics
        </button>
        <button className="navBtn" onClick={() => setPage("ai")}>
          <Settings size={18} /> AI Control
        </button>
      </div>

      {/* MAIN */}
      <div className="main">

        {/* DASHBOARD */}
        {page === "dashboard" && (
          <>
            <h1 className="title">Dashboard</h1>
            <div className="cards">
              <div className="card">
                <Users />
                <h3>Total Customers</h3>
                <p>{customers.length}</p>
              </div>
              <div className="card">
                <Phone />
                <h3>Total Calls</h3>
                <p>{logs.length}</p>
              </div>
              <div className="card">
                <Users />
                <h3>Pending Payments</h3>
                <p>{customers.filter(c => getStatus(c) === "pending").length}</p>
              </div>
            </div>
            <div className="card chart">
              <h3>Payment Status</h3>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie data={chartData} dataKey="value">
                    <Cell fill="#16a34a" />
                    <Cell fill="#ef4444" />
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </>
        )}

        {/* CUSTOMERS */}
        {page === "customers" && (
          <>
            <div className="headerRow">
              <h1 className="title">Customers</h1>
              <button className="addBtn" onClick={() => setShowModal(true)}>
                Add Customer
              </button>
            </div>

            <input
              className="search"
              placeholder="Search customer"
              onChange={(e) => setSearch(e.target.value)}
            />

            <div className="card">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Phone</th>
                    <th>Policy</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Call</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(c => (
                    <tr key={c.id} onClick={() => setSelected(c)}>
                      <td>{c.id}</td>
                      <td>{c.name}</td>
                      <td>{c.phone}</td>
                      <td>{getPolicy(c)}</td>
                      <td>₹{c.due_amount}</td>
                      <td>{getStatus(c)}</td>
                      <td>
                        <button
                          className="callBtn"
                          onClick={(e) => {
                            e.stopPropagation();
                            makeCall(c.id);
                          }}
                        >
                          Call
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* CUSTOMER PROFILE */}
        {selected && (
          <div className="profile">
            <h2>Customer Profile</h2>
            <p><b>Name:</b> {selected.name}</p>
            <p><b>Phone:</b> {selected.phone}</p>
            <p><b>Policy:</b> {getPolicy(selected)}</p>
            <p><b>Amount:</b> ₹{selected.due_amount}</p>
            <p><b>Status:</b> {getStatus(selected)}</p>
            <button onClick={() => setSelected(null)}>Close</button>
          </div>
        )}

        {/* CALL LOGS */}
        {page === "logs" && (
          <div className="card">
            <h1 className="title">Call Logs</h1>
            <table>
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Phone</th>
                  <th>Time</th>
                  <th>Outcome</th>
                  <th>Customer Speech</th>
                  <th>AI Reply</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id}>
                    <td>{getCustomerName(log.customer_id)}</td>
                    <td>{getCustomerPhone(log.customer_id)}</td>
                    <td>{formatTime(log.created_at)}</td>
                    <td>{log.outcome || "—"}</td>
                    <td>{log.customer_text || "—"}</td>
                    <td>{log.ai_response || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ANALYTICS */}
        {page === "analytics" && (
          <div className="card">
            <h1 className="title">Analytics</h1>
            <p>Total Customers: {customers.length}</p>
            <p>Paid: {customers.filter(c => getStatus(c) === "paid").length}</p>
            <p>Pending: {customers.filter(c => getStatus(c) === "pending").length}</p>
            <p>Total Calls Made: {logs.length}</p>
            <p>Escalated: {logs.filter(l => l.escalation_flag).length}</p>
          </div>
        )}

        {/* AI CONTROL */}
        {page === "ai" && (
          <div className="card">
            <h1 className="title">AI Control</h1>
            <button className="controlBtn" onClick={runAI}>
              Trigger Auto Call Now
            </button>
            <p>Manually trigger automated reminder calls to all eligible customers.</p>
          </div>
        )}

      </div>

      {/* ADD CUSTOMER MODAL */}
      {showModal && (
        <div className="modal">
          <div className="modalCard">
            <h2>Add Customer</h2>
            <form onSubmit={addCustomer}>
              <input name="name" placeholder="Name" required />
              <input name="phone" placeholder="Phone (+91XXXXXXXXXX)" required />
              <input name="policy" placeholder="Policy Number" />
              <input name="amount" placeholder="Amount (₹)" required />
              <input name="days" placeholder="Days Until Due" required />
              <button type="submit">Add Customer</button>
              <button type="button" onClick={() => setShowModal(false)}>Cancel</button>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}