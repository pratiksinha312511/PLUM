import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="border-b border-border/80 bg-background/85 backdrop-blur-sm sticky top-0 z-30">
      <div className="editorial-container flex items-center justify-between py-5">
        <Link href="/" className="flex items-baseline gap-3">
          <span className="font-serif text-2xl tracking-tight">Plum</span>
          <span className="small-caps !text-muted-foreground">Claims&nbsp;·&nbsp;Adjudication&nbsp;Console</span>
        </Link>
        <nav className="hidden md:flex items-center gap-8 text-sm">
          <Link href="/" className="text-foreground hover:text-accent transition-colors">Submit</Link>
          <Link href="/claims" className="text-foreground hover:text-accent transition-colors">Claims</Link>
          <Link href="/policy" className="text-foreground hover:text-accent transition-colors">Policy</Link>
          <Link href="/architecture" className="text-foreground hover:text-accent transition-colors">Architecture</Link>
        </nav>
        <Link href="/submit" className="btn btn-primary text-sm">
          New&nbsp;claim
          <span aria-hidden>→</span>
        </Link>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-32 border-t border-border/80">
      <div className="editorial-container py-12 grid gap-6 md:grid-cols-3 text-sm">
        <div>
          <p className="font-serif text-xl mb-2">Plum Claims</p>
          <p className="text-muted-foreground max-w-sm">
            An explainable multi-agent pipeline that adjudicates group health
            insurance claims for{" "}
            <a href="https://www.plumhq.com/" className="link" target="_blank" rel="noreferrer">
              plumhq.com
            </a>
            . Built for the AI Engineer assignment.
          </p>
        </div>
        <div>
          <p className="small-caps mb-3">Endpoints</p>
          <ul className="space-y-2 text-muted-foreground">
            <li><code className="font-mono">POST /api/claims</code></li>
            <li><code className="font-mono">GET /api/claims</code></li>
            <li><code className="font-mono">GET /api/policy</code></li>
          </ul>
        </div>
        <div>
          <p className="small-caps mb-3">Reading</p>
          <ul className="space-y-2 text-muted-foreground">
            <li><Link href="/architecture" className="link">Architecture</Link></li>
            <li><Link href="/policy" className="link">Active policy</Link></li>
            <li><Link href="/claims" className="link">All decisions</Link></li>
          </ul>
        </div>
      </div>
      <div className="editorial-container border-t border-border/60 py-5 text-xs text-muted-foreground flex justify-between">
        <span>© Plum AI Pod — assignment build</span>
        <span className="font-mono">v1.0.0</span>
      </div>
    </footer>
  );
}
