import { clsx } from "clsx";
import { Loader2, X } from "lucide-react";
import { useEffect, useRef } from "react";

const BUTTON_VARIANTS = {
	primary: "bg-fg text-bg hover:bg-fg/85",
	secondary: "border border-border bg-surface hover:bg-subtle",
	ghost: "text-muted hover:bg-subtle hover:text-fg",
	danger: "bg-red-600 text-white hover:bg-red-700",
};

export function Button({
	variant = "secondary",
	icon = false,
	busy = false,
	className,
	children,
	disabled,
	...props
}) {
	return (
		<button
			type="button"
			className={clsx(
				"inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
				icon ? "size-8" : "h-9 px-3",
				BUTTON_VARIANTS[variant],
				className,
			)}
			disabled={disabled || busy}
			{...props}
		>
			{busy && <Loader2 className="size-4 animate-spin" />}
			{children}
		</button>
	);
}

const FIELD =
	"w-full rounded-md border border-border bg-surface px-3 text-sm placeholder:text-muted/70 disabled:opacity-50";

export function Input({ className, ...props }) {
	return <input className={clsx(FIELD, "h-9", className)} {...props} />;
}

export function Textarea({ className, ...props }) {
	return (
		<textarea className={clsx(FIELD, "min-h-20 py-2", className)} {...props} />
	);
}

export function Select({ className, ...props }) {
	return <select className={clsx(FIELD, "h-9", className)} {...props} />;
}

export function Field({ label, hint, className, children }) {
	return (
		// biome-ignore lint/a11y/noLabelWithoutControl: the control is passed in as children
		<label className={clsx("grid content-start gap-1.5 text-sm", className)}>
			<span className="font-medium">{label}</span>
			{children}
			{hint && <span className="text-xs text-muted">{hint}</span>}
		</label>
	);
}

export function Switch({ checked, onChange, label, hint }) {
	return (
		<label className="flex cursor-pointer items-start justify-between gap-4 text-sm">
			<span className="grid gap-0.5">
				<span className="font-medium">{label}</span>
				{hint && <span className="text-xs text-muted">{hint}</span>}
			</span>
			<button
				type="button"
				role="switch"
				aria-checked={checked}
				onClick={() => onChange(!checked)}
				className={clsx(
					"relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors",
					checked ? "bg-accent" : "bg-border",
				)}
			>
				<span
					className={clsx(
						"absolute top-0.5 left-0.5 size-4 rounded-full bg-white shadow transition-transform",
						checked && "translate-x-4",
					)}
				/>
			</button>
		</label>
	);
}

export function Card({ title, action, className, children }) {
	return (
		<section
			className={clsx("rounded-lg border border-border bg-surface", className)}
		>
			{title && (
				<header className="flex items-center justify-between gap-4 border-b border-border px-4 py-3">
					<h2 className="font-semibold">{title}</h2>
					{action}
				</header>
			)}
			{children}
		</section>
	);
}

const BADGE_TONES = {
	neutral: "bg-subtle text-muted",
	green:
		"bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
	red: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
	amber: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
	blue: "bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300",
};

export function Badge({ tone = "neutral", className, children }) {
	return (
		<span
			className={clsx(
				"inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
				BADGE_TONES[tone],
				className,
			)}
		>
			{children}
		</span>
	);
}

export function StockBadge({ inStock }) {
	if (inStock === true) return <Badge tone="green">In stock</Badge>;
	if (inStock === false) return <Badge tone="red">Out of stock</Badge>;
	return <Badge>Stock unknown</Badge>;
}

const DIALOG_SIZES = { md: "max-w-md", lg: "max-w-2xl", xl: "max-w-5xl" };

export function Dialog({ open, onClose, title, size = "md", children }) {
	const ref = useRef(null);

	useEffect(() => {
		const dialog = ref.current;
		if (open && !dialog.open) dialog.showModal();
		if (!open && dialog.open) dialog.close();
	}, [open]);

	return (
		<dialog
			ref={ref}
			onClose={onClose}
			onMouseDown={(event) => event.target === ref.current && onClose()}
			className={clsx(
				"m-auto w-[calc(100%-2rem)] rounded-lg border border-border bg-surface p-0 text-fg shadow-xl",
				DIALOG_SIZES[size],
			)}
		>
			{open && (
				<div className="max-h-[85dvh] overflow-y-auto p-5">
					<div className="mb-4 flex items-start justify-between gap-4">
						<h2 className="text-lg font-semibold">{title}</h2>
						<Button variant="ghost" icon aria-label="Close" onClick={onClose}>
							<X className="size-4" />
						</Button>
					</div>
					{children}
				</div>
			)}
		</dialog>
	);
}

export function ConfirmDialog({
	open,
	onClose,
	title,
	children,
	confirmLabel = "Delete",
	onConfirm,
	busy,
}) {
	return (
		<Dialog open={open} onClose={onClose} title={title}>
			<p className="text-sm text-muted">{children}</p>
			<div className="mt-6 flex justify-end gap-2">
				<Button onClick={onClose}>Cancel</Button>
				<Button variant="danger" busy={busy} onClick={onConfirm}>
					{confirmLabel}
				</Button>
			</div>
		</Dialog>
	);
}

export function EmptyState({ icon: Icon, title, children, action }) {
	return (
		<div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-6 py-16 text-center">
			{Icon && <Icon className="mb-2 size-8 text-muted" />}
			<h2 className="font-semibold">{title}</h2>
			{children && <p className="max-w-sm text-sm text-muted">{children}</p>}
			{action && <div className="mt-4">{action}</div>}
		</div>
	);
}

export function Spinner({ className }) {
	return (
		<Loader2 className={clsx("size-5 animate-spin text-muted", className)} />
	);
}
