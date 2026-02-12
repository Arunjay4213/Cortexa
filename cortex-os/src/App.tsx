import React from 'react';
import {
  Terminal,
  Activity,
  AlertTriangle,
  ArrowRight,
  Database,
  ShieldAlert,
  Cpu,
  Zap,
  Check,
  X,
  Search,
  Server,
  DollarSign,
  Brain,
  Layers,
  Network,
  TrendingDown
} from 'lucide-react';

// --- UTILS ---
function cn(...classes: (string | undefined | null | false)[]) {
  return classes.filter(Boolean).join(' ');
}

// --- SHADCN-STYLE COMPONENTS (Inline Implementation) ---

// 1. Card
const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("rounded-xl border border-zinc-800 bg-black/40 text-zinc-100 shadow-sm", className)} {...props} />
));
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
));
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(({ className, ...props }, ref) => (
  <h3 ref={ref} className={cn("font-semibold leading-none tracking-tight text-zinc-100", className)} {...props} />
));
CardTitle.displayName = "CardTitle";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
));
CardContent.displayName = "CardContent";

// 2. Badge
interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline";
  className?: string;
}
const Badge = ({ className, variant = "default", ...props }: BadgeProps) => {
  const variants = {
    default: "border-transparent bg-zinc-100 text-zinc-900 hover:bg-zinc-100/80",
    secondary: "border-transparent bg-zinc-800 text-zinc-100 hover:bg-zinc-800/80",
    destructive: "border-transparent bg-rose-900 text-zinc-100 hover:bg-rose-900/80",
    outline: "text-zinc-100",
  };
  return (
    <div className={cn("inline-flex items-center rounded-md border border-zinc-700 px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2", variants[variant], className)} {...props} />
  );
};

// 3. Progress
const Progress = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { value: number, indicatorColor?: string }>(({ className, value, indicatorColor = "bg-zinc-100", ...props }, ref) => (
  <div ref={ref} className={cn("relative h-2 w-full overflow-hidden rounded-full bg-zinc-900", className)} {...props}>
    <div className={cn("h-full w-full flex-1 transition-all", indicatorColor)} style={{ transform: `translateX(-${100 - (value || 0)}%)` }} />
  </div>
));
Progress.displayName = "Progress";

// 4. Button
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost" | "link";
  size?: "default" | "sm" | "lg" | "icon";
}
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant = "default", size = "default", ...props }, ref) => {
  const variants = {
    default: "bg-zinc-100 text-zinc-900 hover:bg-zinc-200",
    outline: "border border-zinc-700 bg-transparent hover:bg-zinc-800 text-zinc-100",
    ghost: "hover:bg-zinc-800 text-zinc-100",
    link: "text-zinc-100 underline-offset-4 hover:underline",
  };
  const sizes = {
    default: "h-9 px-4 py-2",
    sm: "h-8 rounded-md px-3 text-xs",
    lg: "h-10 rounded-md px-8",
    icon: "h-9 w-9",
  };
  return (
    <button ref={ref} className={cn("inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-400 disabled:pointer-events-none disabled:opacity-50", variants[variant], sizes[size], className)} {...props} />
  );
});
Button.displayName = "Button";

// 5. Table
const Table = React.forwardRef<HTMLTableElement, React.HTMLAttributes<HTMLTableElement>>(({ className, ...props }, ref) => (
  <div className="relative w-full overflow-auto">
    <table ref={ref} className={cn("w-full caption-bottom text-sm", className)} {...props} />
  </div>
));
Table.displayName = "Table";

const TableHeader = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(({ className, ...props }, ref) => (
  <thead ref={ref} className={cn("[&_tr]:border-b [&_tr]:border-zinc-800", className)} {...props} />
));
TableHeader.displayName = "TableHeader";

const TableBody = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(({ className, ...props }, ref) => (
  <tbody ref={ref} className={cn("[&_tr:last-child]:border-0", className)} {...props} />
));
TableBody.displayName = "TableBody";

const TableRow = React.forwardRef<HTMLTableRowElement, React.HTMLAttributes<HTMLTableRowElement>>(({ className, ...props }, ref) => (
  <tr ref={ref} className={cn("border-b border-zinc-800 transition-colors hover:bg-zinc-900/50 data-[state=selected]:bg-zinc-900", className)} {...props} />
));
TableRow.displayName = "TableRow";

const TableHead = React.forwardRef<HTMLTableCellElement, React.ThHTMLAttributes<HTMLTableCellElement>>(({ className, ...props }, ref) => (
  <th ref={ref} className={cn("h-10 px-4 text-left align-middle font-medium text-zinc-400 [&:has([role=checkbox])]:pr-0", className)} {...props} />
));
TableHead.displayName = "TableHead";

const TableCell = React.forwardRef<HTMLTableCellElement, React.TdHTMLAttributes<HTMLTableCellElement>>(({ className, ...props }, ref) => (
  <td ref={ref} className={cn("p-4 align-middle [&:has([role=checkbox])]:pr-0 font-mono text-xs text-zinc-300", className)} {...props} />
));
TableCell.displayName = "TableCell";

// --- CUSTOM VIZ COMPONENTS ---

const SimpleSparkline = ({ data, color = "#10b981", className }: { data: number[], color?: string, className?: string }) => {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * 100;
    // Invert Y because SVG coordinates top-left is 0,0
    const y = 100 - ((d - min) / ((max - min) || 1)) * 100;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg viewBox="0 0 100 100" className={cn("w-full opacity-20", className)} preserveAspectRatio="none">
      <polyline fill="none" stroke={color} strokeWidth="2" points={points} vectorEffect="non-scaling-stroke" />
    </svg>
  );
};


// --- MAIN APPLICATION ---

export default function App() {
  const scrollToManifesto = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    const element = document.getElementById('manifesto');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-zinc-100 font-sans selection:bg-emerald-500/30 overflow-x-hidden relative">

      {/* Hero Section */}
      <section className="pt-24 pb-16 px-4 relative z-10">
        <div className="max-w-7xl mx-auto flex flex-col items-center text-center space-y-8">

          {/* Logo Replacement */}
          <div className="flex items-center gap-2 mb-4">
            <div className="w-5 h-5 bg-emerald-500 rounded-sm flex items-center justify-center">
              <div className="w-2 h-2 bg-black rounded-full" />
            </div>
            <span className="font-bold tracking-tight text-sm">CortexOS</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white to-zinc-500 max-w-4xl">
            Debug And Optimize <span className="text-white"> <br /> AI Memory.</span>
          </h1>

          <p className="text-xl text-zinc-400 max-w-2xl font-light">
            Turn AI memory into a financial instrument. Track Token ROI, Attribution, and Hallucination Risk per memory unit.
          </p>

          {/* Live Ticker */}
          <div className="flex flex-wrap justify-center gap-4 mt-8">
            <Badge variant="outline" className="border-emerald-500/20 text-emerald-500 h-8 px-4 font-mono text-xs">
              MEM HEALTH: 0.847
            </Badge>
            <Badge variant="outline" className="border-rose-500/20 text-rose-500 h-8 px-4 font-mono text-xs">
              <Activity className="w-3 h-3 mr-2 animate-pulse" />
              TOKEN WASTE: 38.2%
            </Badge>
            <Badge variant="outline" className="border-blue-500/20 text-blue-400 h-8 px-4 font-mono text-xs">
              ATTR CONF: 0.91
            </Badge>
          </div>

          <div className="flex gap-4 mt-8">
            <a
              href="#"
              onClick={(e) => e.preventDefault()}
              className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-400 disabled:pointer-events-none disabled:opacity-50 h-12 px-8 bg-emerald-600 hover:bg-emerald-700 text-white border-0 font-semibold"
            >
              View Interactive Demo
              <ArrowRight className="w-4 h-4 ml-2" />
            </a>
            <a
              href="#manifesto"
              onClick={scrollToManifesto}
              className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-400 disabled:pointer-events-none disabled:opacity-50 h-12 px-8 border border-zinc-800 bg-transparent hover:bg-zinc-800 text-zinc-300 hover:text-white"
            >
              Read the Manifesto
            </a>
          </div>
        </div>
      </section>

      {/* Live Dashboard (Bento Grid) */}
      <section className="py-12 px-4 relative z-10">
        <div className="max-w-7xl mx-auto">
          <div className="border border-zinc-800 bg-zinc-950 rounded-lg overflow-hidden shadow-2xl shadow-emerald-900/10">

            {/* Dashboard Header */}
            <div className="bg-zinc-900 border-b border-zinc-800 p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500/20 border border-red-500/50" />
                  <div className="w-3 h-3 rounded-full bg-amber-500/20 border border-amber-500/50" />
                  <div className="w-3 h-3 rounded-full bg-emerald-500/20 border border-emerald-500/50" />
                </div>
                <span className="ml-3 text-xs font-mono text-zinc-500">dashboard_view.jsx — main</span>
              </div>
              <div className="text-xs font-mono text-zinc-500 flex gap-4">
                <span>CPU: 12%</span>
                <span>MEM: 64%</span>
              </div>
            </div>

            {/* Grid Layout */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-[1px] bg-zinc-800">

              {/* Quadrant 1: Token Economics */}
              <div className="bg-[#0a0a0a] p-6 flex flex-col h-64 relative overflow-hidden">
                <div className="absolute bottom-0 left-0 right-0 h-24 z-0 pointer-events-none">
                  <SimpleSparkline data={[800, 950, 1100, 1050, 1300, 1200, 1400]} color="#ef4444" className="h-full" />
                </div>

                <div className="flex items-center justify-between mb-6 relative z-10">
                  <h3 className="text-xs font-bold text-zinc-400 tracking-wider flex items-center gap-2">
                    <DollarSign className="w-3 h-3" /> TOKEN ECONOMICS
                  </h3>
                  <Badge variant="outline" className="text-[10px] text-zinc-500 border-zinc-800">REALTIME</Badge>
                </div>
                <div className="mt-auto relative z-10">
                  <div className="text-4xl font-mono font-medium text-white mb-1">$1,200<span className="text-lg text-zinc-600">/day</span></div>
                  <div className="text-xs text-zinc-500 mb-4 font-mono">Current burn rate</div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-[10px] font-mono uppercase text-rose-500">
                      <span>Waste Rate</span>
                      <span>38%</span>
                    </div>
                    <Progress value={38} className="h-1.5 bg-zinc-900" indicatorColor="bg-rose-500" />
                  </div>
                </div>
              </div>

              {/* Quadrant 2: Accuracy */}
              <div className="bg-[#0a0a0a] p-6 flex flex-col h-64 relative overflow-hidden">
                <div className="absolute bottom-0 left-0 right-0 h-24 z-0 pointer-events-none">
                  <SimpleSparkline data={[60, 65, 70, 75, 80, 85, 82]} color="#8b5cf6" className="h-full" />
                </div>

                <div className="flex items-center justify-between mb-6 relative z-10">
                  <h3 className="text-xs font-bold text-zinc-400 tracking-wider flex items-center gap-2">
                    <Zap className="w-3 h-3" /> ACCURACY IMPACT
                  </h3>
                </div>

                <div className="mb-6 relative z-10">
                  <div className="text-4xl font-mono font-medium text-violet-400 mb-1">14.2dB</div>
                  <div className="text-xs text-zinc-500 font-mono">Signal-to-Noise Ratio</div>
                </div>

                <div className="space-y-3 mt-auto relative z-10">
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] font-mono text-zinc-400">
                      <span>RAG Precision</span>
                      <span className="text-emerald-500">94%</span>
                    </div>
                    <Progress value={94} className="h-1 bg-zinc-900" indicatorColor="bg-emerald-500" />
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] font-mono text-zinc-400">
                      <span>Ctx Window Eff.</span>
                      <span className="text-violet-500">62%</span>
                    </div>
                    <Progress value={62} className="h-1 bg-zinc-900" indicatorColor="bg-violet-500" />
                  </div>
                </div>
              </div>

              {/* Quadrant 3: Risk Exposure */}
              <div className="bg-[#0a0a0a] p-6 flex flex-col h-64 relative overflow-hidden">
                 <div className="absolute bottom-0 left-0 right-0 h-24 z-0 pointer-events-none">
                  <SimpleSparkline data={[10, 20, 15, 30, 45, 20, 10]} color="#f59e0b" className="h-full" />
                </div>

                <div className="flex items-center justify-between mb-6 relative z-10">
                  <h3 className="text-xs font-bold text-zinc-400 tracking-wider flex items-center gap-2">
                    <AlertTriangle className="w-3 h-3" /> RISK EXPOSURE
                  </h3>
                </div>

                <div className="flex-1 flex flex-col justify-center relative z-10">
                  <div className="flex items-baseline gap-2">
                    <span className="text-4xl font-mono font-medium text-amber-500">-4.2%</span>
                    <span className="text-sm font-mono text-zinc-500">VaR</span>
                  </div>
                  <p className="text-xs text-zinc-500 mt-2 font-mono leading-relaxed">
                    Value at Risk projected based on current hallucination frequency in high-value queries.
                  </p>
                </div>

                <div className="mt-auto pt-4 border-t border-zinc-800 relative z-10">
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-mono text-zinc-400">Staleness Index</span>
                    <Badge variant="destructive" className="bg-rose-950/30 text-rose-500 border-rose-900/50 animate-pulse">
                      HIGH RISK
                    </Badge>
                  </div>
                </div>
              </div>

              {/* Quadrant 4: Trace Visualization (Replaces Table) */}
              <div className="bg-[#0a0a0a] p-0 flex flex-col h-64 overflow-hidden relative">
                <div className="p-6 pb-2 flex items-center justify-between bg-[#0a0a0a] z-10">
                  <h3 className="text-xs font-bold text-zinc-400 tracking-wider flex items-center gap-2">
                    <Network className="w-3 h-3" /> LIVE TRACE #8492
                  </h3>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    <span className="text-[10px] text-red-500 font-mono">HALLUCINATION DETECTED</span>
                  </div>
                </div>

                <div className="flex-1 p-6 pt-2 flex flex-col justify-center gap-4 relative">
                   <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-rose-950/10 via-transparent to-transparent pointer-events-none" />

                   {/* Trace Node 1 */}
                   <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-zinc-900 border border-zinc-700 flex items-center justify-center shrink-0">
                        <Brain className="w-4 h-4 text-zinc-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-[10px] text-zinc-500 font-mono">USER QUERY</div>
                        <div className="text-xs text-zinc-300 truncate font-mono">"Summarize Q3 burn..."</div>
                      </div>
                   </div>

                   <div className="pl-4 h-4 border-l border-dashed border-zinc-700 ml-0.5" />

                   {/* Trace Node 2: Faulty */}
                   <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-rose-950/30 border border-rose-900 flex items-center justify-center shrink-0 relative">
                        <Database className="w-4 h-4 text-rose-500" />
                        <div className="absolute -right-1 -top-1 w-2 h-2 bg-rose-500 rounded-full" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-[10px] text-rose-500 font-mono font-bold flex justify-between">
                          <span>BAD RETRIEVAL (ID: #47)</span>
                          <span>92% CONF</span>
                        </div>
                        <div className="text-xs text-rose-400 truncate font-mono">Outdated_Draft_v2.pdf</div>
                      </div>
                      <Button size="sm" variant="outline" className="h-6 text-[10px] border-rose-900 text-rose-500 hover:bg-rose-950 hover:text-rose-400">
                        Fix
                      </Button>
                   </div>

                   <div className="pl-4 h-4 border-l border-dashed border-zinc-700 ml-0.5" />

                   {/* Trace Node 3 */}
                   <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-zinc-900 border border-zinc-700 flex items-center justify-center shrink-0">
                         <Terminal className="w-4 h-4 text-zinc-500" />
                      </div>
                       <div className="flex-1 min-w-0">
                        <div className="text-[10px] text-zinc-500 font-mono">RESPONSE GENERATED</div>
                      </div>
                   </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      </section>

      {/* Competitor Gap Table */}
      <section className="py-16 px-4 bg-zinc-900/20 relative z-10">
        <div className="max-w-4xl mx-auto">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold tracking-tight mb-4">Memory Systems vs. CortexOS</h2>
            <p className="text-zinc-400">Why enterprise agents need financial-grade memory infrastructure.</p>
          </div>

          <div className="rounded-xl border border-zinc-800 overflow-hidden bg-[#0a0a0a]">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-[40%] text-zinc-300 pl-6">Capability</TableHead>
                  <TableHead className="w-[30%] text-zinc-500">Memo / Zep</TableHead>
                  <TableHead className="w-[30%] text-emerald-500 font-bold bg-emerald-950/10">CortexOS</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow className="border-zinc-800/50">
                  <TableCell className="font-sans text-sm font-medium text-zinc-300 pl-6">Store & Retrieve Memories</TableCell>
                  <TableCell className="text-zinc-400">
                    <div className="flex items-center gap-2 text-zinc-400"><Check className="w-4 h-4 text-emerald-500" /> Yes</div>
                  </TableCell>
                  <TableCell className="bg-emerald-950/5">
                    <div className="flex items-center gap-2 text-zinc-100"><Check className="w-4 h-4 text-emerald-500" /> Yes (Wrapper)</div>
                  </TableCell>
                </TableRow>
                <TableRow className="border-zinc-800/50">
                  <TableCell className="font-sans text-sm font-medium text-zinc-300 pl-6">Per-Memory Attribution</TableCell>
                  <TableCell className="text-zinc-600">
                    <div className="flex items-center gap-2 text-zinc-400"><X className="w-4 h-4 text-rose-500" /> No</div>
                  </TableCell>
                  <TableCell className="bg-emerald-950/5">
                    <div className="flex items-center gap-2 text-zinc-100"><Check className="w-4 h-4 text-emerald-500" /> Yes (Shapley Values)</div>
                  </TableCell>
                </TableRow>
                <TableRow className="border-zinc-800/50">
                  <TableCell className="font-sans text-sm font-medium text-zinc-300 pl-6">Token Cost & ROI</TableCell>
                  <TableCell className="text-zinc-600">
                    <div className="flex items-center gap-2 text-zinc-400"><X className="w-4 h-4 text-rose-500" /> No</div>
                  </TableCell>
                  <TableCell className="bg-emerald-950/5">
                    <div className="flex items-center gap-2 text-zinc-100"><Check className="w-4 h-4 text-emerald-500" /> Yes (Financial Metrics)</div>
                  </TableCell>
                </TableRow>
                <TableRow className="border-zinc-800/50">
                  <TableCell className="font-sans text-sm font-medium text-zinc-300 pl-6">Hallucination Root Cause</TableCell>
                  <TableCell className="text-zinc-600">
                    <div className="flex items-center gap-2 text-zinc-400"><X className="w-4 h-4 text-rose-500" /> No</div>
                  </TableCell>
                  <TableCell className="bg-emerald-950/5">
                    <div className="flex items-center gap-2 text-zinc-100"><Check className="w-4 h-4 text-emerald-500" /> Yes (Trace to ID)</div>
                  </TableCell>
                </TableRow>
                <TableRow className="border-transparent">
                  <TableCell className="font-sans text-sm font-medium text-zinc-300 pl-6">GDPR Provenance Graph</TableCell>
                  <TableCell className="text-zinc-600">
                    <div className="flex items-center gap-2 text-zinc-400"><X className="w-4 h-4 text-rose-500" /> No</div>
                  </TableCell>
                  <TableCell className="bg-emerald-950/5">
                    <div className="flex items-center gap-2 text-zinc-100"><Check className="w-4 h-4 text-emerald-500" /> Yes (Cascading Delete)</div>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </div>
      </section>

      {/* ROI Footer Argument (Replacement) */}
      <section className="py-20 px-4 bg-zinc-900/30 border-t border-zinc-800 relative z-10">
        <div className="max-w-4xl mx-auto text-center mb-12">
          <h2 className="text-3xl font-bold text-white mb-4">The Cost of <span className="text-rose-500">Silent Failures</span></h2>
          <p className="text-zinc-400 max-w-2xl mx-auto">
            Most teams don't realize that 30-40% of retrieved tokens are irrelevant.
            At scale, "good enough" memory infrastructure is a six-figure liability.
          </p>
        </div>

        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-8">

          {/* Card 1: The Problem (Red) */}
          <Card className="bg-[#0a0a0a] border-rose-900/30 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-24 bg-rose-500/5 rounded-full blur-3xl group-hover:bg-rose-500/10 transition-colors" />
            <CardHeader>
              <div className="flex items-center justify-between mb-2">
                 <Badge variant="outline" className="border-rose-500/20 text-rose-500 bg-rose-500/5">Current State</Badge>
                 <TrendingDown className="text-rose-500 w-5 h-5" />
              </div>
              <CardTitle className="text-xl">Unoptimized RAG Pipeline</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex justify-between items-baseline border-b border-zinc-800 pb-4">
                <span className="text-zinc-500 font-mono text-sm">Token Waste Rate</span>
                <span className="text-rose-500 font-mono font-bold">~35%</span>
              </div>
              <div className="flex justify-between items-baseline border-b border-zinc-800 pb-4">
                <span className="text-zinc-500 font-mono text-sm">Hallucination Rate</span>
                <span className="text-rose-500 font-mono font-bold">2-5%</span>
              </div>
              <div className="pt-2">
                <div className="text-xs text-zinc-500 font-mono mb-1">PROJECTED LOSS (100k queries/day)</div>
                <div className="text-3xl font-mono text-white">$38,325<span className="text-lg text-zinc-600">/yr</span></div>
              </div>
            </CardContent>
          </Card>

          {/* Card 2: The Solution (Emerald) */}
          <Card className="bg-[#0a0a0a] border-emerald-900/30 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-24 bg-emerald-500/5 rounded-full blur-3xl group-hover:bg-emerald-500/10 transition-colors" />
            <CardHeader>
              <div className="flex items-center justify-between mb-2">
                 <Badge variant="outline" className="border-emerald-500/20 text-emerald-500 bg-emerald-500/5">With CortexOS</Badge>
                 <Zap className="text-emerald-500 w-5 h-5" />
              </div>
              <CardTitle className="text-xl">Financial-Grade Memory</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex justify-between items-baseline border-b border-zinc-800 pb-4">
                <span className="text-zinc-500 font-mono text-sm">Waste Identification</span>
                <span className="text-emerald-500 font-mono font-bold">100%</span>
              </div>
              <div className="flex justify-between items-baseline border-b border-zinc-800 pb-4">
                <span className="text-zinc-500 font-mono text-sm">Attribution Depth</span>
                <span className="text-emerald-500 font-mono font-bold">Per-Token</span>
              </div>
              <div className="pt-2">
                <div className="text-xs text-zinc-500 font-mono mb-1">NET RECOVERY</div>
                <div className="text-3xl font-mono text-white">$14,000<span className="text-lg text-zinc-600">/mo</span></div>
              </div>
            </CardContent>
          </Card>

        </div>
      </section>

      {/* Manifesto Section */}
      <section id="manifesto" className="py-24 px-4 relative z-10 bg-zinc-950/50 border-t border-zinc-900">
        <div className="max-w-3xl mx-auto">
          <div className="border border-zinc-800 bg-[#0a0a0a] p-8 md:p-12 rounded-xl relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-20">
               <Terminal className="w-12 h-12 text-zinc-700" />
            </div>

            <h2 className="text-2xl md:text-3xl font-bold text-white mb-8 tracking-tight font-sans">
              THE END OF <span className="text-emerald-500">"VIBES-BASED"</span> ENGINEERING
            </h2>

            <div className="space-y-6 text-zinc-400 font-mono text-sm leading-relaxed text-justify">
              <p>
                Every serious AI agent ships with persistent memory. We treat it as standard infrastructure—a "vector database" to store and retrieve context. But this mental model is fundamentally broken.
              </p>
              <p>
                In finance, a "portfolio" is not just a database of stocks. It is a living collection of assets, each with a Cost Basis, a Return on Investment (ROI), and a Value at Risk (VaR). You do not manage a portfolio by "feeling" like it’s doing well. You manage it by looking at the P&L.
              </p>
              <p>
                Today, AI engineers manage memory by gut feel. We inject tokens into the context window and hope they help. We have no idea which memories caused a hallucination, which ones are costing us money but contributing zero signal, or which contradictory memories are silently degrading performance.
              </p>
              <p className="text-white font-bold border-l-2 border-emerald-500 pl-4">
                This is the "Black Box" era of agentic memory.
              </p>
              <p>
                CortexOS is the first step into the Financial Era of memory. We believe that every token has a cost, and every retrieved memory must prove its return. We are not building a better database. We are building the ticker tape, the risk desk, and the audit trail for the most expensive resource in the AI stack: Context.
              </p>
              <p className="pt-4 text-emerald-500 font-bold">
                Stop debugging by intuition. Start optimizing by attribution.
              </p>
            </div>

            <div className="mt-8 pt-8 border-t border-zinc-900 flex justify-between items-center text-xs font-mono text-zinc-600">
              <span>DOC_ID: MANIFESTO_V1</span>
              <span>ENCRYPTION: NONE</span>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-900 py-10 text-center relative z-10 bg-[#0a0a0a]">
        <div className="max-w-7xl mx-auto px-4 flex flex-col items-center">
          <div className="w-6 h-6 bg-zinc-800 rounded-sm flex items-center justify-center mb-4">
            <div className="w-2 h-2 bg-zinc-500 rounded-full" />
          </div>
          <p className="text-white text-sm mb-2 font-mono">
            © 2026 CortexOS Inc. San Francisco, CA.
            <span className="block text-zinc-400 text-xs mt-1">(If this says 2024, please debug your context window)</span>
          </p>
        </div>
      </footer>

    </div>
  );
}
