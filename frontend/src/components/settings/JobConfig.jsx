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
		mutationFn: async ({ key, value }) => {
			await axios.post(`${API_URL}/jobs/config`, {
				key: key,
				value: value.toString(),
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
	const [localForecastInterval, setLocalForecastInterval] = React.useState(
		jobConfig.forecasting_interval_hours || 24,
	);

	// Sync local state when remote data changes
	React.useEffect(() => {
		setLocalInterval(jobConfig.refresh_interval_minutes);
		setLocalForecastInterval(jobConfig.forecasting_interval_hours || 24);
	}, [jobConfig]);

	const handleSave = () => {
		updateJobConfigMutation.mutate({
			key: "refresh_interval_minutes",
			value: localInterval,
		});
		updateJobConfigMutation.mutate({
			key: "forecasting_interval_hours",
			value: localForecastInterval,
		});
	};

	const triggerForecastMutation = useMutation({
		mutationFn: async () => {
			await axios.post(`${API_URL}/jobs/refresh-forecast`);
		},
		onSuccess: () => {
			toast.success("Forecasting job triggered");
		},
		onError: () => {
			toast.error("Failed to trigger forecasting");
		},
	});

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
					<Label>Global Default Refresh Interval (Minutes)</Label>
					<p className="text-sm text-muted-foreground">
						Default refresh rate for items that don't have a specific interval
						or profile assigned.
					</p>
					<Input
						type="number"
						min="1"
						value={localInterval}
						onChange={(e) => setLocalInterval(e.target.value)}
					/>
				</div>

				<div className="space-y-2 pt-4 border-t">
					<Label>Forecasting Interval (Hours)</Label>
					<p className="text-sm text-muted-foreground">
						How often to retrain and update price forecasts.
					</p>
					<div className="flex gap-2">
						<Input
							type="number"
							min="1"
							value={localForecastInterval}
							onChange={(e) => setLocalForecastInterval(e.target.value)}
						/>
					</div>
				</div>
				<div className="text-sm text-muted-foreground space-y-1">
					<p>Status: {jobConfig.running ? "Running" : "Idle"}</p>
				</div>
				<div className="flex gap-2">
					<Button
						onClick={handleSave}
						disabled={updateJobConfigMutation.isPending}
					>
						Save Configuration
					</Button>
					<Button
						variant="secondary"
						onClick={() => triggerForecastMutation.mutate()}
						disabled={triggerForecastMutation.isPending}
					>
						Run Forecast Now
					</Button>
				</div>
			</CardContent>
		</Card>
	);
}
