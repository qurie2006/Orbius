export default function AnalysisTrace({
  events,
  running,
  router,
  routerStatus,
  clock,
  simulate,
  onFastForward,
  onToggleSimulation,
  formatAgentName,
}) {
  const hasEvents = events.length > 0;

  return (
    <section className="panel analysis-trace" aria-label="Analysis trace and controls">
      <header className="analysis-trace__header">
        <div>
          <span className="analysis-trace__eyebrow">PIPELINE / ACTIVITY</span>
          <h2>Analysis trace</h2>
        </div>
        <span className={`analysis-trace__run-state ${running ? "is-live" : ""}`} role="status">
          <span className="analysis-trace__run-dot" aria-hidden="true" />
          {running ? "Live run" : hasEvents ? "Recorded run" : "Awaiting input"}
        </span>
      </header>

      {router?.active_model && (
        <p className="analysis-trace__route">
          {routerStatus} · <strong>{router.active_model}</strong>
          {router.fallback && <span className="analysis-trace__fallback">Fallback</span>}
        </p>
      )}

      {hasEvents ? (
        <ol className="analysis-trace__events" aria-live={running ? "polite" : undefined}>
          {events.map((event, index) => {
            const active = running && event.status === "running";
            const recorded = !running && event.status === "running";
            const completed = event.status === "complete" || event.status === "completed";
            return (
              <li
                className={`analysis-trace__event ${active ? "is-live" : ""} ${completed ? "is-complete" : ""}`}
                key={`${event.agent}-${event.task}-${index}`}
              >
                <span className={`analysis-trace__level ${active ? "is-live" : ""}`}>L{event.level}</span>
                <div className="analysis-trace__event-copy">
                  <strong>{formatAgentName(event.agent)}</strong>
                  <span>{event.task}</span>
                </div>
                <span
                  className={`analysis-trace__event-status ${active ? "is-live" : recorded ? "is-recorded" : ""}`}
                  title={recorded ? "This status was recorded during the run; it is not a current activity indicator." : undefined}
                >
                  {recorded ? "Recorded as running" : event.status || "Status not reported"}
                </span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="analysis-trace__empty">
          Run analysis to see the events reported by the processing pipeline.
        </p>
      )}

      <footer className="analysis-trace__controls">
        <span className="analysis-trace__eyebrow">DEMO CONTROLS</span>
        <div className="analysis-trace__control-row">
          <button type="button" className="btn ghost" onClick={onFastForward}>
            Fast-forward 30 days
          </button>
          <button
            type="button"
            className={`btn ghost ${simulate ? "is-simulated" : ""}`}
            aria-pressed={simulate}
            onClick={onToggleSimulation}
          >
            {simulate ? "Quota simulation on" : "Simulate quota failure"}
          </button>
        </div>
        {clock?.now && (
          <span className="analysis-trace__clock">
            Demo clock · {new Date(clock.now).toUTCString()} · +{Math.round(clock.offset_days || 0)}d
          </span>
        )}
      </footer>
    </section>
  );
}
