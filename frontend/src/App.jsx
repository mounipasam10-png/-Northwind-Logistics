import { useEffect, useState } from "react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function App() {
  const [file, setFile] = useState(null);
  const [receipt, setReceipt] = useState(null);
  const [verdict, setVerdict] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [selectedEmployee, setSelectedEmployee] = useState("");
  const [question, setQuestion] = useState("");
  const [policyAnswer, setPolicyAnswer] = useState(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [overrideResult, setOverrideResult] = useState(null);
  const [verdicts, setVerdicts] = useState([]);
  const [overrides, setOverrides] = useState([]);
  const [loading, setLoading] = useState("");

  useEffect(() => {
    loadEmployees();
    loadHistory();
  }, []);

  async function loadEmployees() {
    const res = await fetch(`${API}/employees`);
    setEmployees(await res.json());
  }

  async function loadHistory() {
    const verdictRes = await fetch(`${API}/verdicts`);
    const overrideRes = await fetch(`${API}/overrides`);

    setVerdicts(await verdictRes.json());
    setOverrides(await overrideRes.json());
  }

  function currentEmployee() {
    return employees.find((e) => e.employee_id === selectedEmployee);
  }

  async function extractReceipt() {
    if (!file) return alert("Choose a receipt first");

    setLoading("Extracting receipt...");

    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API}/receipts/extract`, {
      method: "POST",
      body: formData,
    });

    setReceipt(await res.json());
    setLoading("");
  }

  async function runAdjudication() {
    if (!receipt?.parsed) return alert("Extract receipt first");

    const emp = currentEmployee();

    if (!emp) return alert("Select an employee first");

    setLoading("Running adjudication...");

    const res = await fetch(`${API}/adjudicate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        receipt: {
          id: receipt.receipt_id,
          ...receipt.parsed,
        },
        employee: {
          employee_id: emp.employee_id,
          name: emp.name,
          grade: emp.grade,
          title: emp.title,
          department: emp.department,
          home_base: emp.home_base,
        },
        submission: {
          trip_purpose: "Business travel",
        },
      }),
    });

    const data = await res.json();

    setVerdict(data);
    setLoading("");
    loadHistory();
  }

  async function overrideVerdict() {
    if (!verdict?.verdict_id) return alert("Run adjudication first");

    setLoading("Saving override...");

    const res = await fetch(`${API}/override`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        verdict_id: verdict.verdict_id,
        reviewer: "Reviewer",
        new_status: "approved",
        reason: overrideReason || "Approved after manual review",
      }),
    });

    setOverrideResult(await res.json());
    setLoading("");
    loadHistory();
  }

  async function askPolicy() {
    if (!question.trim()) return alert("Enter a policy question");

    setLoading("Asking policy library...");

    const res = await fetch(`${API}/policies/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question }),
    });

    setPolicyAnswer(await res.json());
    setLoading("");
  }

  return (
    <div className="page">
      <header>
        <h1>Northwind AI Expense Review</h1>
        <p>
          Reviewer dashboard for receipt extraction, adjudication, overrides,
          and policy Q&A.
        </p>
      </header>

      {loading && <div className="loading">{loading}</div>}

      <section className="card">
        <h2>1. Select Employee</h2>

        <select
          value={selectedEmployee}
          onChange={(e) => setSelectedEmployee(e.target.value)}
        >
          <option value="">Select employee...</option>

          {employees.map((emp) => (
            <option key={emp.employee_id} value={emp.employee_id}>
              {emp.name} — {emp.title} — Grade {emp.grade}
            </option>
          ))}
        </select>
      </section>

      <section className="card">
        <h2>2. Upload Receipt</h2>

        <input type="file" onChange={(e) => setFile(e.target.files[0])} />

        <button onClick={extractReceipt}>Extract Receipt</button>

        {receipt && (
          <div className="result">
            <h3>Extracted Receipt</h3>

            <p>
              <b>Merchant:</b> {receipt.parsed?.merchant}
            </p>

            <p>
              <b>Amount:</b> ${receipt.parsed?.amount}
            </p>

            <p>
              <b>Category:</b> {receipt.parsed?.category}
            </p>

            <p>
              <b>Location:</b> {receipt.parsed?.location}
            </p>

            <pre>{JSON.stringify(receipt.parsed, null, 2)}</pre>
          </div>
        )}
      </section>

      <section className="card">
        <h2>3. Run Adjudication</h2>

        <button onClick={runAdjudication}>Adjudicate Receipt</button>

        {verdict && (
          <div>
            <div className={`status ${verdict.status}`}>
              {verdict.status}
            </div>

            <p>
              <b>Confidence:</b> {verdict.confidence}
            </p>

            <p>{verdict.reasoning}</p>

            <h3>Violations</h3>

            {verdict.violations?.length ? (
              verdict.violations.map((v, i) => (
                <div className="violation" key={i}>
                  <b>{v.rule}</b>

                  <p>
                    Non-reimbursable amount: ${v.receipt_value}
                  </p>

                  <p>
                    Flagged amount: ${v.flagged_amount}
                  </p>
                </div>
              ))
            ) : (
              <p>No violations.</p>
            )}

            <h3>Citations</h3>

            {verdict.citations?.map((c, i) => (
              <blockquote key={i}>
                {c.quoted_text}
                <br />
                <small>
                  {c.policy_id} §{c.section}
                </small>
              </blockquote>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h2>4. Human Override</h2>

        <textarea
          placeholder="Reason for override"
          value={overrideReason}
          onChange={(e) => setOverrideReason(e.target.value)}
        />

        <button onClick={overrideVerdict}>Approve Override</button>

        {overrideResult && (
          <div className="override-box">
            Override saved. New status:{" "}
            <b>{overrideResult.updated_status}</b>
          </div>
        )}
      </section>

      <section className="card">
        <h2>5. Ask Policy Library</h2>

        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Can alcohol be reimbursed during solo travel?"
        />

        <button onClick={askPolicy}>Ask Policy</button>

        {policyAnswer && (
          <div className="result">
            <p>{policyAnswer.answer}</p>

            <p>
              <b>Confidence:</b> {policyAnswer.confidence}
            </p>

            {policyAnswer.citations?.map((c, i) => (
              <blockquote key={i}>
                {c.quoted_text}
                <br />
                <small>
                  {c.policy_id} §{c.section}
                </small>
              </blockquote>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h2>6. History</h2>

        <h3>Saved Verdicts</h3>

        {verdicts.map((v) => (
          <div className="history-row" key={v.id}>
            <b>#{v.id}</b> —{" "}
            <span className={`mini ${v.status}`}>{v.status}</span>

            <p>{v.reasoning}</p>
          </div>
        ))}

        <h3>Overrides</h3>

        {overrides.map((o) => (
          <div className="history-row" key={o.id}>
            Verdict #{o.verdict_id}: {o.original_status} → {o.new_status}
            <p>{o.reason}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

export default App;