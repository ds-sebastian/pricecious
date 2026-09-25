import { ExternalLink } from "lucide-react";
import { Dialog } from "@/components/ui";
import { formatDateTime } from "@/format";

export function ScreenshotDialog({ item, onClose }) {
	return (
		<Dialog open={!!item} onClose={onClose} title={item?.name} size="xl">
			{item && (
				<>
					<a href={item.screenshot_url} target="_blank" rel="noreferrer">
						<img
							src={item.screenshot_url}
							alt={`Screenshot of ${item.name}`}
							className="w-full rounded-md border border-border"
						/>
					</a>
					<p className="mt-3 flex items-center justify-between gap-4 text-xs text-muted">
						<span>
							{item.last_checked &&
								`What the browser saw on ${formatDateTime(item.last_checked)}`}
						</span>
						<a
							href={item.screenshot_url}
							target="_blank"
							rel="noreferrer"
							className="inline-flex items-center gap-1 hover:text-fg"
						>
							Full size <ExternalLink className="size-3" />
						</a>
					</p>
				</>
			)}
		</Dialog>
	);
}
