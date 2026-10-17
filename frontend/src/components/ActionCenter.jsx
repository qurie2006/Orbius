function CalendarPanel({ days, selectedDate, onSelectDate, selectedEvents }) {
  return (
    <div className="calendar-widget">
      <div className="calendar-header">
        <strong>Calendar</strong>
        <span className="muted">{selectedDate}</span>
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
          <CalendarPanel days={days} selectedDate={selectedDate} onSelectDate={onSelectDate} selectedEvents={selectedEvents} />
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
            </div>
          </section>
        )}
      </div>
    </aside>
  );
}
