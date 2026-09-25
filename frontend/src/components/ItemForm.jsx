import { useEffect, useRef, useState } from "react";
import { api, useAction, useProfiles } from "@/api";
import {
	Button,
	Dialog,
	Field,
	Input,
	Select,
	Switch,
	Textarea,
} from "@/components/ui";

const TEXT_FIELDS = [
	"url",
	"name",
	"currency",
	"tags",
	"selector",
	"custom_prompt",
	"description",
];
const NUMBER_FIELDS = [
	"target_price",
	"current_price",
	"check_interval_minutes",
	"notification_profile_id",
];

function toForm(item = {}) {
	const form = { is_active: item.is_active ?? true };
	for (const key of [...TEXT_FIELDS, ...NUMBER_FIELDS]) {
		form[key] = item[key] == null ? "" : String(item[key]);
	}
	form.in_stock = item.in_stock == null ? "" : String(item.in_stock);
	return form;
}

function toPayload(form) {
	const payload = {
		...form,
		in_stock: form.in_stock === "" ? null : form.in_stock === "true",
	};
	for (const key of NUMBER_FIELDS) {
		payload[key] = form[key] === "" ? null : Number(form[key]);
	}
	return payload;
}

/** item: an existing item to edit, or a draft without an id (e.g. { url }) to add. */
export function ItemFormDialog({ item, open, onClose }) {
	return (
		<Dialog
			open={open}
			onClose={onClose}
			title={item?.id ? "Edit item" : "Add item"}
			size="lg"
		>
			<ItemForm item={item} onDone={onClose} />
		</Dialog>
	);
}

function ItemForm({ item, onDone }) {
	const isNew = !item?.id;
	const [form, setForm] = useState(() => toForm(item));
	const { data: profiles = [] } = useProfiles();
	const set = (key) => (event) =>
		setForm({ ...form, [key]: event.target.value });

	const save = useAction(
		async (payload) => {
			if (!isNew) return api.put(`/items/${item.id}`, payload);
			const created = await api.post("/items", payload);
			await api.post(`/items/${created.id}/check`).catch(() => {}); // the scheduler picks it up otherwise
			return created;
		},
		{
			success: isNew ? "Item added, checking it now" : "Item saved",
			invalidate: [["items"], ["analytics"], ["history"]],
			onSuccess: onDone,
		},
	);

	const profile = profiles.find(
		(p) => String(p.id) === form.notification_profile_id,
	);

	return (
		<form
			className="grid gap-4"
			onSubmit={(event) => {
				event.preventDefault();
				save.mutate(toPayload(form));
			}}
		>
			<Field label="Product page" hint={isNew && <Bookmarklet />}>
				<Input
					type="url"
					required
					autoFocus={isNew && !form.url}
					placeholder="https://store.example/product"
					value={form.url}
					onChange={set("url")}
				/>
			</Field>
			<Field label="Name">
				<Input
					placeholder="Leave empty to use the page title"
					value={form.name}
					onChange={set("name")}
				/>
			</Field>
			<div className="grid gap-4 sm:grid-cols-2">
				<Field
					label="Target price"
					hint="Get notified when the price drops to this."
				>
					<Input
						type="number"
						min="0"
						step="0.01"
						inputMode="decimal"
						value={form.target_price}
						onChange={set("target_price")}
					/>
				</Field>
				<Field label="Notifications">
					<Select
						value={form.notification_profile_id}
						onChange={set("notification_profile_id")}
					>
						<option value="">None</option>
						{profiles.map((p) => (
							<option key={p.id} value={p.id}>
								{p.name}
							</option>
						))}
					</Select>
				</Field>
			</div>
			<Field
				label="Tags"
				hint="Comma separated. Items sharing a tag can be compared."
			>
				<Input
					placeholder="gpu, living room"
					value={form.tags}
					onChange={set("tags")}
				/>
			</Field>
			{!isNew && (
				<Switch
					label="Scheduled checks"
					hint="Paused items are only checked when you ask."
					checked={form.is_active}
					onChange={(is_active) => setForm({ ...form, is_active })}
				/>
			)}

			<details className="group rounded-md border border-border">
				<summary className="cursor-pointer px-3 py-2 text-sm font-medium select-none">
					Advanced
				</summary>
				<div className="grid gap-4 border-t border-border p-3">
					<div className="grid gap-4 sm:grid-cols-2">
						<Field
							label="Check every (minutes)"
							hint={
								profile
									? `Default: ${profile.check_interval_minutes} (from ${profile.name})`
									: "Default: the global interval in Settings"
							}
						>
							<Input
								type="number"
								min="5"
								value={form.check_interval_minutes}
								onChange={set("check_interval_minutes")}
							/>
						</Field>
						<Field
							label="Price element (CSS selector)"
							hint="Scrolled into view before the screenshot."
						>
							<Input
								placeholder=".product-price"
								value={form.selector}
								onChange={set("selector")}
							/>
						</Field>
						<Field label="Currency" hint="Detected on the first check.">
							<Input
								placeholder="USD"
								maxLength={3}
								pattern="[A-Za-z]{3}"
								title="A three-letter currency code, such as EUR"
								value={form.currency}
								onChange={set("currency")}
							/>
						</Field>
					</div>
					<Field
						label="Instructions for the AI"
						hint='For tricky pages, e.g. "Use the price of the 2 TB model, not the 1 TB one."'
					>
						<Textarea
							value={form.custom_prompt}
							onChange={set("custom_prompt")}
						/>
					</Field>
					<Field label="Notes">
						<Textarea value={form.description} onChange={set("description")} />
					</Field>
					{!isNew && (
						<div className="grid gap-4 sm:grid-cols-2">
							<Field
								label="Current price"
								hint="Correct a bad reading. Also the baseline for outlier checks."
							>
								<Input
									type="number"
									min="0"
									step="0.01"
									value={form.current_price}
									onChange={set("current_price")}
								/>
							</Field>
							<Field label="Stock">
								<Select value={form.in_stock} onChange={set("in_stock")}>
									<option value="">Unknown</option>
									<option value="true">In stock</option>
									<option value="false">Out of stock</option>
								</Select>
							</Field>
						</div>
					)}
				</div>
			</details>

			<div className="flex justify-end gap-2 pt-2">
				<Button onClick={onDone}>Cancel</Button>
				<Button type="submit" variant="primary" busy={save.isPending}>
					{isNew ? "Add item" : "Save"}
				</Button>
			</div>
		</form>
	);
}

/** A link to drag to the bookmarks bar that opens this dialog for the page being viewed. */
function Bookmarklet() {
	const link = useRef(null);
	useEffect(() => {
		// React refuses javascript: URLs in JSX, so set it directly.
		const target = `${window.location.origin}/?add=`;
		link.current.setAttribute(
			"href",
			`javascript:void(window.open(${JSON.stringify(target)}+encodeURIComponent(location.href)))`,
		);
	}, []);
	return (
		<>
			Tip: drag{" "}
			<a
				ref={link}
				href="#bookmarklet"
				title="Drag this to your bookmarks bar"
				className="rounded border border-border px-1.5 py-0.5 font-medium text-fg"
			>
				+ Pricecious
			</a>{" "}
			to your bookmarks bar, then click it on any product page.
		</>
	);
}
