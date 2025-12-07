import { AIConfig } from "@/components/settings/AIConfig";
import { JobConfig } from "@/components/settings/JobConfig";
import { NotificationProfiles } from "@/components/settings/NotificationProfiles";
import { ScraperConfig } from "@/components/settings/ScraperConfig";
import React from "react";

export default function Settings() {
	return (
		<div className="space-y-6 animate-in fade-in duration-500 max-w-5xl mx-auto pb-10">
			<div>
				<h2 className="text-2xl font-bold tracking-tight">Settings</h2>
				<p className="text-muted-foreground">
					Configure application preferences and notifications.
				</p>
			</div>

			<AIConfig />
			<ScraperConfig />
			<JobConfig />
			<NotificationProfiles />
		</div>
	);
}
