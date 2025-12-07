import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { API_URL } from "@/lib/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { Clock } from "lucide-react";
import React from "react";
import { toast } from "sonner";

export function JobConfig() {
	const queryClient = useQueryClient();

	const { data: jobConfig = { refresh_interval_minutes: 60, running: false } } =
		useQuery({
			queryKey: ["jobConfig"],
			queryFn: async () => {
				const res = await axios.get(`${API_URL}/jobs/config`);
				return res.data;
			},
		});

	const updateJobConfigMutation = useMutation({
		mutationFn: async (newInterval) => {
			await axios.post(`${API_URL}/jobs/config`, {
				key: "refresh_interval_minutes",
				value: newInterval.toString(),
			});
		},
		onSuccess: () => {
			toast.success("Job configuration updated");
			queryClient.invalidateQueries({ queryKey: ["jobConfig"] });
		},
		onError: () => {
			toast.error("Failed to update job config");
		},
	});

	const [localInterval, setLocalInterval] = React.useState(
		jobConfig.refresh_interval_minutes,
	);

	// Sync local state when remote data changes
	React.useEffect(() => {
		setLocalInterval(jobConfig.refresh_interval_minutes);
	}, [jobConfig.refresh_interval_minutes]);

	const handleSave = () => {
		updateJobConfigMutation.mutate(localInterval);
	};

	return (
		<Card>
			<CardHeader>
				<CardTitle className="flex items-center gap-2">
					<Clock className="h-5 w-5" />
					Automated Refresh Job
				</CardTitle>
				<CardDescription>
					Configure the background job that checks for price updates.
				</CardDescription>
			</CardHeader>
			<CardContent className="space-y-4">
				<div className="space-y-2">
					<Label>Default Refresh Interval (Minutes)</Label>
					<p className="text-sm text-muted-foreground">
						Used when no specific interval is set on the item or its profile.
					</p>
					<Input
						type="number"
						min="1"
						value={localInterval}
						onChange={(e) => setLocalInterval(e.target.value)}
					/>
				</div>
				<div className="text-sm text-muted-foreground space-y-1">
					<p>Status: {jobConfig.running ? "Running" : "Idle"}</p>
				</div>
				<Button
					onClick={handleSave}
					disabled={updateJobConfigMutation.isPending}
				>
					Save Job Config
				</Button>
			</CardContent>
		</Card>
	);
}
