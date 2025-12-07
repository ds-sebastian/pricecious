import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useSettings } from "@/hooks/use-settings";
import { Settings as SettingsIcon } from "lucide-react";
import React from "react";

export function ScraperConfig() {
	const { settings, updateSetting } = useSettings();

	const smart_scroll_enabled = settings.smart_scroll_enabled === "true";
	const smart_scroll_pixels = Number.parseInt(
		settings.smart_scroll_pixels || "350",
	);
	const text_context_enabled = settings.text_context_enabled === "true";
	const text_context_length = Number.parseInt(
		settings.text_context_length || "5000",
	);
	const scraper_timeout = Number.parseInt(settings.scraper_timeout || "90000");

	return (
		<Card>
			<CardHeader>
				<CardTitle className="flex items-center gap-2">
					<SettingsIcon className="h-5 w-5" />
					Scraper Configuration
				</CardTitle>
				<CardDescription>
					Configure how the scraper interacts with web pages.
				</CardDescription>
			</CardHeader>
			<CardContent className="space-y-4">
				<div className="flex items-center justify-between">
					<div>
						<Label>Smart Scroll</Label>
						<p className="text-sm text-muted-foreground">
							Scroll down to trigger lazy loading.
						</p>
					</div>
					<Switch
						checked={smart_scroll_enabled}
						onCheckedChange={(checked) =>
							updateSetting("smart_scroll_enabled", checked)
						}
					/>
				</div>
				{smart_scroll_enabled && (
					<div className="space-y-2">
						<Label>Scroll Pixels</Label>
						<Input
							type="number"
							value={smart_scroll_pixels}
							onChange={(e) =>
								updateSetting(
									"smart_scroll_pixels",
									Number.parseInt(e.target.value),
								)
							}
						/>
					</div>
				)}
				<div className="flex items-center justify-between">
					<div>
						<Label>Text Context</Label>
						<p className="text-sm text-muted-foreground">
							Send page text to AI along with screenshot.
						</p>
					</div>
					<Switch
						checked={text_context_enabled}
						onCheckedChange={(checked) =>
							updateSetting("text_context_enabled", checked)
						}
					/>
				</div>
				{text_context_enabled && (
					<div className="space-y-2">
						<Label>Max Text Length</Label>
						<Input
							type="number"
							value={text_context_length}
							onChange={(e) =>
								updateSetting(
									"text_context_length",
									Number.parseInt(e.target.value),
								)
							}
						/>
					</div>
				)}
				<div className="space-y-2">
					<Label>Timeout (ms)</Label>
					<Input
						type="number"
						value={scraper_timeout}
						onChange={(e) =>
							updateSetting("scraper_timeout", Number.parseInt(e.target.value))
						}
					/>
				</div>
			</CardContent>
		</Card>
	);
}
