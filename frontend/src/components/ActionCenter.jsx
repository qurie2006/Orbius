function CalendarPanel({ days, selectedDate, onSelectDate, selectedEvents, calendarMonth, setCalendarMonth, calendarEvents }) {
  const monthLabel = calendarMonth
    ? new Date(calendarMonth.year, calendarMonth.month).toLocaleString("default", { month: "short", year: "numeric" })
    : "Calendar";

  return (
    <div className="calendar-widget">
      <div className="calendar-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <strong>{monthLabel}</strong>
          {setCalendarMonth && (
            <div style={{ display: "flex", gap: 4 }}>
              <button
                type="button"
                className="btn ghost"
                style={{ padding: "2px 6px", fontSize: "0.72rem" }}
                onClick={() => setCalendarMonth((prev) => {
                  let m = prev.month - 1;
                  let y = prev.year;
                  if (m < 0) { m = 11; y -= 1; }
                  return { year: y, month: m };
                })}
                title="Previous Month"
              >
                ◀
              </button>
              <button
                type="button"
                className="btn ghost"
                style={{ padding: "2px 6px", fontSize: "0.72rem" }}
                onClick={() => setCalendarMonth((prev) => {
                  let m = prev.month + 1;
                  let y = prev.year;
                  if (m > 11) { m = 0; y += 1; }
                  return { year: y, month: m };
                })}
                title="Next Month"
              >
                ▶
              </button>
            </div>
          )}
        </div>
        <span className="muted" style={{ fontSize: "0.78rem" }}>{selectedDate}</span>
      </div>
      <div className="calendar-days-header" aria-hidden="true">
        <span>S</span><span>M</span><span>T</span><span>W</span><span>T</span><span>F</span><span>S</span>
      </div>
      <div className="calendar-grid">
        {days.map((day) => (
          <button
            type="button"
            key={day.day}
            className={`calendar-cell ${selectedDate === day.dateStr ? "selected" : ""}`}
            aria-pressed={selectedDate === day.dateStr}
            aria-label={`${day.dateStr}${day.evs.length ? `, ${day.evs.length} scheduled items` : ""}`}
            onClick={() => onSelectDate(day.dateStr)}
          >
            {day.day}
            {(day.hasUrgent || day.hasWarning || day.hasNormal) && (
              <span className="dot-indicator" aria-hidden="true">
                {day.hasUrgent && <span className="dot-urgent" />}
                {day.hasWarning && <span className="dot-warning" />}
                {day.hasNormal && <span className="dot-normal" />}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Document Deadlines & Milestones with Click-to-Jump */}
      {calendarEvents && (
        <div style={{ marginTop: 14, borderTop: "1px solid var(--line)", paddingTop: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span className="requirements-document__eyebrow" style={{ margin: 0, fontSize: "0.72rem" }}>
              DOCUMENT DEADLINES ({calendarEvents.length})
            </span>
            <span className="muted" style={{ fontSize: "0.7rem" }}>Click to jump</span>
          </div>
          {calendarEvents.length === 0 ? (
            <p className="muted" style={{ fontSize: "0.76rem", margin: 0 }}>No deadlines extracted yet.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 5, maxHeight: 150, overflowY: "auto" }}>
              {calendarEvents.map((ev) => {
                const isSelected = selectedDate === ev.date;
                return (
                  <button
                    key={ev.id}
                    type="button"
                    style={{
                      padding: "6px 8px",
                      borderRadius: 6,
                      background: isSelected ? "color-mix(in srgb, var(--accent) 18%, transparent)" : "var(--elev-2)",
                      border: isSelected ? "1px solid var(--accent)" : "1px solid var(--line)",
                      cursor: "pointer",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 8,
                      textAlign: "left",
                      color: "inherit",
                      width: "100%",
                    }}
                    onClick={() => {
                      onSelectDate(ev.date);
                      if (setCalendarMonth && ev.date) {
                        const parts = ev.date.split("-");
                        if (parts.length >= 2) {
                          setCalendarMonth({ year: parseInt(parts[0], 10), month: parseInt(parts[1], 10) - 1 });
                        }
                      }
                    }}
                  >
                    <div style={{ overflow: "hidden", minWidth: 0 }}>
                      <strong style={{ fontSize: "0.78rem", display: "block", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                        {ev.title}
                      </strong>
                      <span className="muted" style={{ fontSize: "0.68rem", fontStyle: "italic", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", display: "block" }}>
                        {ev.source_span || ev.detail}
                      </span>
                    </div>
                    <code style={{ fontSize: "0.72rem", color: "var(--accent-text)", fontWeight: 700, flexShrink: 0 }}>
                      {ev.date}
                    </code>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      <section className="action-center__selected-day">
        <h3>Scheduled · {selectedEvents.length}</h3>
        {selectedEvents.length === 0 ? (
          <p className="muted">No tasks or alerts scheduled for this date.</p>
        ) : selectedEvents.map((event) => (
          <article className="action-center__item" key={event.id}>
            <div className="action-center__item-heading">
              <strong>{event.title}</strong>
              <span className={`action-center__badge is-${event.urgency}`}>
                {event.urgency === "urgent" ? "Due today" :
                  event.urgency === "due_tomorrow" ? "Due tomorrow" :
                    event.urgency === "completed" ? "Completed" : event.urgency}
              </span>
            </div>
            <p>{event.detail}</p>
            {event.source_span && <p className="muted">Source · {event.source_span}</p>}
          </article>
        ))}
      </section>
    </div>
  );
}

function InboxPanel({ drafts, onAct }) {
  if (!drafts.length) {
    return <p className="muted">No drafts yet. Ingest documents and generate requirements to detect action items.</p>;
  }

  return drafts.map((task) => (
    <article className="action-center__item" key={task.id}>
      <div className="action-center__item-heading">
        <strong>{task.payload?.subject || task.context}</strong>
        {task.status === "pending" && <span className="action-center__badge is-pending">Action required</span>}
      </div>
      {task.payload?.recipient && <p className="muted">For · {task.payload.recipient}</p>}
      {task.payload?.body && <p>{task.payload.body}</p>}
      {task.source_span && <p className="action-center__evidence">Evidence · {task.source_span}</p>}
      {task.status === "pending" ? (
        <div className="row">
          <button type="button" className="btn primary" onClick={() => onAct(task, "approved")}>
            Approve draft
          </button>
          <button type="button" className="btn" onClick={() => onAct(task, "dismissed")}>
            Dismiss
          </button>
        </div>
      ) : (
        <p className="muted">Status · {task.status}</p>
      )}
    </article>
  ));
}

function TimelinePanel({ alerts }) {
  if (!alerts.length) return <p className="muted">No follow-ups scheduled.</p>;

  return alerts.map((alert) => (
    <article className="action-center__item" key={alert.id}>
      <div className="action-center__item-heading">
        <strong>{alert.context}</strong>
        <span className={`action-center__badge ${alert.status === "fired" ? "is-urgent" : "is-scheduled"}`}>
          {alert.status === "fired" ? "Needs attention" : "Scheduled"}
        </span>
      </div>
      <p>{alert.target_date} · <em>{alert.original_phrase}</em></p>
      <p>{alert.reminder_message}</p>
      <p className="muted">Status · {alert.status}</p>
    </article>
  ));
}

export default function ActionCenter({
  tab,
  onTabChange,
  days,
  selectedDate,
  onSelectDate,
  selectedEvents,
  drafts,
  alerts,
  state,
  sessionId,
  onAct,
  calendarMonth,
  setCalendarMonth,
  calendarEvents,
  onJiraPush,
  pushingJira,
}) {
  return (
    <aside className="panel panel-actions action-center">
      <header className="action-center__header">
        <div>
          <span className="requirements-document__eyebrow">OPERATIONS</span>
          <h2>Action center</h2>
        </div>
      </header>
      <div className="action-center__tabs" role="tablist" aria-label="Action center views">
        {[
          ["inbox", "Inbox"],
          ["timeline", "Timeline"],
          ["calendar", "Calendar"],
        ].map(([id, label]) => (
          <button
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={tab === id ? "active" : ""}
            key={id}
            onClick={() => onTabChange(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="action-center__content">
        {tab === "calendar" ? (
          <CalendarPanel
            days={days}
            selectedDate={selectedDate}
            onSelectDate={onSelectDate}
            selectedEvents={selectedEvents}
            calendarMonth={calendarMonth}
            setCalendarMonth={setCalendarMonth}
            calendarEvents={calendarEvents}
          />
        ) : tab === "inbox" ? (
          <InboxPanel drafts={drafts} onAct={onAct} />
        ) : (
          <TimelinePanel alerts={alerts} />
        )}

        {state?.changelog && (
          <p className="action-center__changelog">
            Version {state.version} · {state.changelog.at(-1)?.summary}
          </p>
        )}

        {state && (
          <section className="action-center__exports">
            <span className="requirements-document__eyebrow">EXPORT DELIVERABLES</span>
            <div className="action-center__export-links">
              <a className="btn" href={`/api/export/${sessionId}`} download>Markdown</a>
              <a className="btn primary" href={`/api/export/${sessionId}/pdf`} download>PDF</a>
              <a className="btn" href={`/api/export/${sessionId}/docx`} download>Word</a>
              <a className="btn" href={`/api/export/${sessionId}/jira`} download title="Export issues for Jira import">Jira CSV</a>
              <a className="btn" href={`/api/export/${sessionId}/linear`} download title="Export issues for Linear import">Linear JSON</a>
              {onJiraPush && (
                <button
                  type="button"
                  className="btn"
                  style={{ background: "#0052cc", color: "#fff", border: "none" }}
                  disabled={pushingJira}
                  onClick={onJiraPush}
                  title="Directly push to Jira Cloud REST API"
                >
                  {pushingJira ? "Pushing..." : "🚀 Push to Jira Cloud"}
                </button>
              )}
            </div>
          </section>
        )}
      </div>
    </aside>
  );
}
