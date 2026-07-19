export function Loading() { return <div className="panel loading">Loading operational data…</div>; }
export function ErrorState({ message }: { message: string }) { return <div className="panel error-banner">{message}</div>; }
export function Empty({ message }: { message: string }) { return <div className="empty">{message}</div>; }
