import { useQueryClient } from "@tanstack/react-query";
import { Bell, Pencil, Plus, Send, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, useAction, useProfiles, useSettings } from "@/api";
import {
	Badge,
	Button,
	Card,
	ConfirmDialog,
	Dialog,
	Field,
	Input,
	Select,
	Spinner,
	Switch,
} from "@/components/ui";

const SECRET_MASK = "********";
const PROVIDERS = {
	ollama: { label: "Ollama (local)", model: "gemma3:4b" },
	openai: { label: "OpenAI", model: "gpt-5-mini" },
	anthropic: { label: "Anthropic", model: "claude-haiku-4-5" },
	gemini: { label: "Google Gemini", model: "gemini-2.5-flash" },
	openrouter: { label: "OpenRouter", model: "google/gemini-2.5-flash" },
};
// Settings stored in other units than shown: displayed value = stored value / scale.
const SCALES = {
	scraper_timeout: 1000,
	confidence_threshold_price: 0.01,
	confidence_threshold_stock: 0.01,
};
const round = (value) => Number(value.toFixed(6));

function toForm(saved) {
	const form = { ...saved };
	for (const [key, scale] of Object.entries(SCALES))
		form[key] = round(saved[key] / scale);
	return form;
}

function changedValues(form, saved) {
	const changes = {};
	for (const [key, value] of Object.entries(form)) {
		let parsed = value;
		if (typeof saved[key] === "number") {
			parsed =
				value === "" ? Number.NaN : round(Number(value) * (SCALES[key] ?? 1));
		}
		if (parsed !== saved[key]) changes[key] = parsed;
	}
	return changes;
}

export default function Settings() {
	const { data: saved } = useSettings();
	return (
		<div className="mx-auto grid max-w-3xl gap-6 pb-24">
			<h1 className="text-2xl font-semibold">Settings</h1>
			{saved ? (
				<SettingsForm saved={saved} />
			) : (
				<Spinner className="mx-auto my-12" />
			)}
			<NotificationProfiles />
		</div>
	);
}

function SettingsForm({ saved }) {
	const queryClient = useQueryClient();
	const [form, setForm] = useState(() => toForm(saved));
	const changes = changedValues(form, saved);
	const dirty = Object.keys(changes).length > 0;
	const provider = form.ai_provider;

	const save = useAction(() => api.put("/settings", changes), {
		success: "Settings saved",
		onSuccess: (result) => {
			queryClient.setQueryData(["settings"], result);
			setForm(toForm(result));
		},
	});
	const forecast = useAction(() => api.post("/forecasts/refresh"), {
		success: ({ started }) =>
			started
				? "Updating forecasts in the background"
				: "Forecasts are already updating",
	});

	const value = (key) => ({
		value: form[key],
		onChange: (event) => setForm({ ...form, [key]: event.target.value }),
	});
	const number = (key, props) => ({
		type: "number",
		required: true,
		...value(key),
		...props,
	});
	const toggle = (key) => ({
		checked: form[key],
		onChange: (checked) => setForm({ ...form, [key]: checked }),
	});
	const hasSavedKey = form.ai_api_key === SECRET_MASK;

	return (
		<form
			className="grid gap-6"
			onSubmit={(event) => {
				event.preventDefault();
				save.mutate();
			}}
		>
			<Card title="AI model">
				<div className="grid gap-4 p-4 sm:grid-cols-2">
					<Field label="Provider">
						<Select {...value("ai_provider")}>
							{Object.entries(PROVIDERS).map(([key, { label }]) => (
								<option key={key} value={key}>
									{label}
								</option>
							))}
						</Select>
					</Field>
					<Field label="Model" hint="Must accept images.">
						<Input
							required
							placeholder={PROVIDERS[provider]?.model}
							{...value("ai_model")}
						/>
					</Field>
					<Field label="API key">
						<Input
							type="password"
							autoComplete="off"
							placeholder={
								hasSavedKey
									? "Saved; type to replace"
									: provider === "ollama"
										? "Not needed for Ollama"
										: ""
							}
							value={hasSavedKey ? "" : form.ai_api_key}
							onChange={(event) =>
								setForm({ ...form, ai_api_key: event.target.value })
							}
						/>
					</Field>
					<Field
						label="Base URL"
						hint="For Ollama or other OpenAI-compatible servers."
					>
						<Input
							placeholder={
								provider === "ollama"
									? "http://ollama:11434"
									: "Provider default"
							}
							{...value("ai_api_base")}
						/>
					</Field>
				</div>
				<details className="border-t border-border">
					<summary className="cursor-pointer px-4 py-3 text-sm font-medium select-none">
						Advanced
					</summary>
					<div className="grid gap-4 px-4 pb-4 sm:grid-cols-2">
						<Field label="Temperature" hint="Lower is more deterministic.">
							<Input
								{...number("ai_temperature", { min: 0, max: 2, step: 0.1 })}
							/>
						</Field>
						<Field label="Max output tokens">
							<Input {...number("ai_max_tokens", { min: 16 })} />
						</Field>
						<Field label="Timeout (seconds)">
							<Input {...number("ai_timeout", { min: 1 })} />
						</Field>
						{provider === "openai" && (
							<Field
								label="Reasoning effort"
								hint="For reasoning models such as GPT-5."
							>
								<Select {...value("ai_reasoning_effort")}>
									<option value="minimal">Minimal</option>
									<option value="low">Low</option>
									<option value="medium">Medium</option>
									<option value="high">High</option>
								</Select>
							</Field>
						)}
					</div>
				</details>
			</Card>

			<Card title="Checks">
				<div className="grid gap-4 p-4 sm:grid-cols-2">
					<Field
						label="Check every (minutes)"
						hint="For items without their own interval or a notification profile."
					>
						<Input {...number("refresh_interval_minutes", { min: 5 })} />
					</Field>
					<Field label="Pause an item after" hint="Consecutive failed checks.">
						<Input {...number("max_consecutive_failures", { min: 1 })} />
					</Field>
					<Field
						label="Minimum price confidence (%)"
						hint="Less certain readings are recorded but don't change the price."
					>
						<Input
							{...number("confidence_threshold_price", { min: 0, max: 100 })}
						/>
					</Field>
					<Field label="Minimum stock confidence (%)">
						<Input
							{...number("confidence_threshold_stock", { min: 0, max: 100 })}
						/>
					</Field>
					<Field label="Ignore prices below">
						<Input {...number("price_min_floor", { min: 0, step: "any" })} />
					</Field>
					<Field label="Ignore prices above">
						<Input {...number("price_max_ceiling", { min: 0, step: "any" })} />
					</Field>
				</div>
				<div className="grid gap-4 border-t border-border p-4">
					<Switch
						label="Reject sudden price jumps"
						hint="Protects against misreads, like a price picked up from another product."
						{...toggle("price_outlier_threshold_enabled")}
					/>
					{form.price_outlier_threshold_enabled && (
						<Field
							label="Largest believable change (%)"
							className="sm:w-1/2 sm:pr-2"
						>
							<Input
								{...number("price_outlier_threshold_percent", { min: 1 })}
							/>
						</Field>
					)}
				</div>
			</Card>

			<Card title="Browser">
				<div className="grid gap-4 p-4">
					<Field
						label="Page load timeout (seconds)"
						className="sm:w-1/2 sm:pr-2"
					>
						<Input {...number("scraper_timeout", { min: 1 })} />
					</Field>
					<Switch
						label="Scroll before the screenshot"
						hint="Helps pages that load content lazily."
						{...toggle("smart_scroll_enabled")}
					/>
					{form.smart_scroll_enabled && (
						<Field
							label="Scroll distance (pixels)"
							className="sm:w-1/2 sm:pr-2"
						>
							<Input {...number("smart_scroll_pixels", { min: 0 })} />
						</Field>
					)}
					<Switch
						label="Send page text to the AI"
						hint="Improves accuracy on busy pages, at the cost of more tokens."
						{...toggle("text_context_enabled")}
					/>
					{form.text_context_enabled && (
						<Field
							label="Characters of page text to read"
							className="sm:w-1/2 sm:pr-2"
						>
							<Input {...number("text_context_length", { min: 0 })} />
						</Field>
					)}
				</div>
			</Card>

			<Card title="Forecasts">
				<div className="flex flex-wrap items-end gap-4 p-4">
					<Field label="Update every (hours)" className="w-full sm:w-1/2">
						<Input {...number("forecasting_interval_hours", { min: 1 })} />
					</Field>
					<Button busy={forecast.isPending} onClick={() => forecast.mutate()}>
						Update now
					</Button>
				</div>
			</Card>

			{dirty && (
				<div className="fixed inset-x-0 bottom-0 z-10 border-t border-border bg-surface/95 backdrop-blur">
					<div className="mx-auto flex max-w-3xl items-center justify-end gap-2 px-4 py-3">
						<span className="mr-auto text-sm text-muted">Unsaved changes</span>
						<Button onClick={() => setForm(toForm(saved))}>Discard</Button>
						<Button type="submit" variant="primary" busy={save.isPending}>
							Save changes
						</Button>
					</div>
				</div>
			)}
		</form>
	);
}

function NotificationProfiles() {
	const { data: profiles } = useProfiles();
	const [editing, setEditing] = useState(null); // a profile, "new", or null
	const [deleting, setDeleting] = useState(null);
	const test = useAction(
		(profile) => api.post(`/notification-profiles/${profile.id}/test`),
		{
			success: "Test notification sent",
		},
	);
	const remove = useAction(
		(profile) => api.delete(`/notification-profiles/${profile.id}`),
		{
			success: "Profile deleted",
			invalidate: [["profiles"], ["items"]],
			onSuccess: () => setDeleting(null),
		},
	);

	return (
		<Card
			title="Notifications"
			action={
				<Button onClick={() => setEditing("new")}>
					<Plus className="size-4" /> Add profile
				</Button>
			}
		>
			{!profiles ? (
				<Spinner className="mx-auto my-8" />
			) : profiles.length === 0 ? (
				<div className="flex flex-col items-center gap-2 px-6 py-10 text-center text-sm text-muted">
					<Bell className="size-6" />
					<p className="max-w-sm">
						Profiles send alerts through{" "}
						<a
							href="https://github.com/caronc/apprise/wiki"
							target="_blank"
							rel="noreferrer"
							className="underline hover:text-fg"
						>
							Apprise
						</a>{" "}
						to Discord, Telegram, email and many more. Choose a profile when
						editing an item.
					</p>
				</div>
			) : (
				<ul>
					{profiles.map((profile) => (
						<li
							key={profile.id}
							className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-4 py-3 last:border-0"
						>
							<div className="min-w-0 flex-1">
								<div className="font-medium">{profile.name}</div>
								<div className="truncate text-xs text-muted">
									{profile.apprise_url}
								</div>
								<div className="mt-2 flex flex-wrap gap-1">
									{profile.notify_on_price_drop && (
										<Badge>
											Drops of {profile.price_drop_threshold_percent}%+
										</Badge>
									)}
									{profile.notify_on_target_price && (
										<Badge>Target price</Badge>
									)}
									{profile.notify_on_stock_change && (
										<Badge>Stock changes</Badge>
									)}
									<Badge>
										Checks every {profile.check_interval_minutes} min
									</Badge>
								</div>
							</div>
							<div className="flex">
								<Button
									variant="ghost"
									icon
									aria-label={`Send a test to ${profile.name}`}
									title="Send test"
									disabled={test.isPending}
									onClick={() => test.mutate(profile)}
								>
									<Send className="size-4" />
								</Button>
								<Button
									variant="ghost"
									icon
									aria-label={`Edit ${profile.name}`}
									title="Edit"
									onClick={() => setEditing(profile)}
								>
									<Pencil className="size-4" />
								</Button>
								<Button
									variant="ghost"
									icon
									aria-label={`Delete ${profile.name}`}
									title="Delete"
									onClick={() => setDeleting(profile)}
								>
									<Trash2 className="size-4" />
								</Button>
							</div>
						</li>
					))}
				</ul>
			)}

			<Dialog
				open={editing !== null}
				onClose={() => setEditing(null)}
				title={
					editing === "new"
						? "New notification profile"
						: "Edit notification profile"
				}
			>
				<ProfileForm
					profile={editing === "new" ? undefined : editing}
					onDone={() => setEditing(null)}
				/>
			</Dialog>
			<ConfirmDialog
				open={!!deleting}
				title="Delete profile?"
				onClose={() => setDeleting(null)}
				onConfirm={() => remove.mutate(deleting)}
				busy={remove.isPending}
			>
				Items using “{deleting?.name}” will stop sending notifications.
			</ConfirmDialog>
		</Card>
	);
}

const NEW_PROFILE = {
	name: "",
	apprise_url: "",
	notify_on_price_drop: true,
	price_drop_threshold_percent: 10,
	notify_on_target_price: true,
	notify_on_stock_change: true,
	check_interval_minutes: 60,
};

function ProfileForm({ profile, onDone }) {
	const [form, setForm] = useState(profile ?? NEW_PROFILE);
	const set = (key) => (event) =>
		setForm({ ...form, [key]: event.target.value });
	const toggle = (key) => ({
		checked: form[key],
		onChange: (checked) => setForm({ ...form, [key]: checked }),
	});
	const payload = {
		...form,
		price_drop_threshold_percent: Number(form.price_drop_threshold_percent),
		check_interval_minutes: Number(form.check_interval_minutes),
	};

	const save = useAction(
		() =>
			profile
				? api.put(`/notification-profiles/${profile.id}`, payload)
				: api.post("/notification-profiles", payload),
		{ success: "Profile saved", invalidate: [["profiles"]], onSuccess: onDone },
	);
	// The saved URL is never sent to the browser, so an unchanged one is tested server-side.
	const test = useAction(
		() =>
			profile && form.apprise_url === profile.apprise_url
				? api.post(`/notification-profiles/${profile.id}/test`)
				: api.post("/notification-profiles/test", {
						apprise_url: form.apprise_url,
					}),
		{ success: "Test notification sent" },
	);

	return (
		<form
			className="grid gap-4"
			onSubmit={(event) => {
				event.preventDefault();
				save.mutate();
			}}
		>
			<Field label="Name">
				<Input
					required
					placeholder="Phone"
					value={form.name}
					onChange={set("name")}
				/>
			</Field>
			<Field
				label="Apprise URL"
				hint={
					<>
						For example <code>discord://webhook_id/webhook_token</code> or{" "}
						<code>tgram://bot_token/chat_id</code>.
					</>
				}
			>
				<Input
					required
					value={form.apprise_url}
					onChange={set("apprise_url")}
				/>
			</Field>
			<div className="grid gap-3 rounded-md border border-border p-3">
				<Switch label="Price drops" {...toggle("notify_on_price_drop")} />
				{form.notify_on_price_drop && (
					<Field label="Minimum drop (%)">
						<Input
							type="number"
							min="0.1"
							max="100"
							step="any"
							required
							value={form.price_drop_threshold_percent}
							onChange={set("price_drop_threshold_percent")}
						/>
					</Field>
				)}
				<Switch
					label="Target price reached"
					hint="When an item first drops to its target price."
					{...toggle("notify_on_target_price")}
				/>
				<Switch label="Stock changes" {...toggle("notify_on_stock_change")} />
			</div>
			<Field
				label="Check items every (minutes)"
				hint="Applies to items that use this profile."
			>
				<Input
					type="number"
					min="5"
					required
					value={form.check_interval_minutes}
					onChange={set("check_interval_minutes")}
				/>
			</Field>
			<div className="flex flex-wrap justify-end gap-2 pt-2">
				<Button
					className="mr-auto"
					busy={test.isPending}
					disabled={!form.apprise_url}
					onClick={() => test.mutate()}
				>
					{!test.isPending && <Send className="size-4" />}
					Send test
				</Button>
				<Button onClick={onDone}>Cancel</Button>
				<Button type="submit" variant="primary" busy={save.isPending}>
					Save
				</Button>
			</div>
		</form>
	);
}
