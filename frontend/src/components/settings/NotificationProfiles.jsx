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
import { Switch } from "@/components/ui/switch";
import { API_URL, testNotificationProfile } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
	Bell,
	CheckCircle2,
	Clock,
	DollarSign,
	Edit2,
	Trash2,
	TrendingDown,
	Send,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

export function NotificationProfiles() {
	const queryClient = useQueryClient();
	const [editingProfileId, setEditingProfileId] = useState(null);
	const [newProfile, setNewProfile] = useState({
		name: "",
		apprise_url: "",
		check_interval_minutes: 60,
		notify_on_price_drop: true,
		notify_on_target_price: true,
		price_drop_threshold_percent: 10,
		notify_on_stock_change: true,
	});

	const { data: profiles = [] } = useQuery({
		queryKey: ["profiles"],
		queryFn: async () => {
			const res = await axios.get(`${API_URL}/notification-profiles`);
			return res.data;
		},
	});

	const upsertProfileMutation = useMutation({
		mutationFn: async (profile) => {
			if (editingProfileId) {
				await axios.put(
					`${API_URL}/notification-profiles/${editingProfileId}`,
					profile,
				);
			} else {
				await axios.post(`${API_URL}/notification-profiles`, profile);
			}
		},
		onSuccess: () => {
			toast.success(editingProfileId ? "Profile updated" : "Profile created");
			queryClient.invalidateQueries({ queryKey: ["profiles"] });
			resetForm();
		},
		onError: () => {
			toast.error(
				editingProfileId
					? "Failed to update profile"
					: "Failed to create profile",
			);
		},
	});

	const deleteProfileMutation = useMutation({
		mutationFn: async (id) => {
			await axios.delete(`${API_URL}/notification-profiles/${id}`);
		},
		onSuccess: () => {
			toast.success("Profile deleted");
			queryClient.invalidateQueries({ queryKey: ["profiles"] });
			if (editingProfileId) resetForm();
		},
		onError: () => {
			toast.error("Failed to delete profile");
		},
	});

	// - [x] Explore codebase for notification logic <!-- id: 0 -->
	// - [x] Backend: Implement `test_notification` logic and endpoint <!-- id: 1 -->
	// - [/] Frontend: Add "Test" button to Notification Profile UI <!-- id: 2 -->
	// - [ ] Validate changes <!-- id: 3 -->
	const testProfileMutation = useMutation({
		mutationFn: testNotificationProfile,
		onSuccess: () => toast.success("Test notification sent"),
		onError: () => toast.error("Failed to send test notification"),
	});

	const handleTest = (url) => {
		if (!url) {
			toast.error("Please enter an Apprise URL first");
			return;
		}
		testProfileMutation.mutate(url);
	};

	const resetForm = () => {
		setNewProfile({
			name: "",
			apprise_url: "",
			check_interval_minutes: 60,
			notify_on_price_drop: true,
			notify_on_target_price: true,
			price_drop_threshold_percent: 10,
			notify_on_stock_change: true,
		});
		setEditingProfileId(null);
	};

	const handleEdit = (profile) => {
		setNewProfile({
			name: profile.name,
			apprise_url: profile.apprise_url,
			check_interval_minutes: profile.check_interval_minutes,
			notify_on_price_drop: profile.notify_on_price_drop,
			notify_on_target_price: profile.notify_on_target_price,
			price_drop_threshold_percent: profile.price_drop_threshold_percent,
			notify_on_stock_change: profile.notify_on_stock_change,
		});
		setEditingProfileId(profile.id);
		const form = document.getElementById("profile-form");
		if (form) form.scrollIntoView({ behavior: "smooth" });
	};

	const handleSubmit = (e) => {
		e.preventDefault();
		upsertProfileMutation.mutate(newProfile);
	};

	const handleDelete = (id) => {
		if (confirm("Are you sure you want to delete this profile?")) {
			deleteProfileMutation.mutate(id);
		}
	};

	return (
		<Card>
			<CardHeader>
				<CardTitle className="flex items-center gap-2">
					<Bell className="h-5 w-5" />
					Notification Profiles
				</CardTitle>
				<CardDescription>
					Manage notification settings for different groups of items.
				</CardDescription>
			</CardHeader>
			<CardContent className="space-y-8">
				<form
					id="profile-form"
					onSubmit={handleSubmit}
					className="space-y-4 border-b pb-8"
				>
					<div className="flex items-center justify-between">
						<h4 className="text-sm font-medium">
							{editingProfileId ? "Edit Profile" : "Create New Profile"}
						</h4>
						{editingProfileId && (
							<Button
								type="button"
								variant="ghost"
								size="sm"
								onClick={resetForm}
							>
								Cancel Edit
							</Button>
						)}
					</div>
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="space-y-2">
							<Label>Name</Label>
							<Input
								required
								value={newProfile.name}
								onChange={(e) =>
									setNewProfile({ ...newProfile, name: e.target.value })
								}
								placeholder="e.g., Email Alerts"
							/>
						</div>
						<div className="space-y-2">
							<Label>Apprise URL</Label>
							<div className="flex gap-2">
								<Input
									required
									value={newProfile.apprise_url}
									onChange={(e) =>
										setNewProfile({
											...newProfile,
											apprise_url: e.target.value,
										})
									}
									placeholder="mailto://user:pass@gmail.com"
								/>
								<Button
									type="button"
									variant="outline"
									size="icon"
									onClick={() => handleTest(newProfile.apprise_url)}
									title="Send Test Notification"
									disabled={testProfileMutation.isPending}
								>
									<Send className="h-4 w-4" />
								</Button>
							</div>
						</div>
					</div>
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="space-y-2">
							<Label>Refresh Interval (Minutes)</Label>
							<Input
								type="number"
								min="1"
								value={newProfile.check_interval_minutes}
								onChange={(e) =>
									setNewProfile({
										...newProfile,
										check_interval_minutes: Number.parseInt(e.target.value),
									})
								}
							/>
						</div>
						<div className="space-y-2">
							<Label>Price Drop Threshold (%)</Label>
							<Input
								type="number"
								min="1"
								max="100"
								value={newProfile.price_drop_threshold_percent}
								onChange={(e) =>
									setNewProfile({
										...newProfile,
										price_drop_threshold_percent: Number.parseFloat(
											e.target.value,
										),
									})
								}
							/>
						</div>
					</div>
					<div className="flex flex-wrap gap-4">
						<div className="flex items-center space-x-2">
							<Switch
								checked={newProfile.notify_on_price_drop}
								onCheckedChange={(checked) =>
									setNewProfile({
										...newProfile,
										notify_on_price_drop: checked,
									})
								}
							/>
							<Label>Notify on Drop</Label>
						</div>
						<div className="flex items-center space-x-2">
							<Switch
								checked={newProfile.notify_on_target_price}
								onCheckedChange={(checked) =>
									setNewProfile({
										...newProfile,
										notify_on_target_price: checked,
									})
								}
							/>
							<Label>Notify on Target</Label>
						</div>
						<div className="flex items-center space-x-2">
							<Switch
								checked={newProfile.notify_on_stock_change}
								onCheckedChange={(checked) =>
									setNewProfile({
										...newProfile,
										notify_on_stock_change: checked,
									})
								}
							/>
							<Label>Notify on Stock Change</Label>
						</div>
					</div>
					<Button type="submit" disabled={upsertProfileMutation.isPending}>
						{editingProfileId ? "Update Profile" : "Create Profile"}
					</Button>
				</form>

				<div className="space-y-4">
					<h4 className="text-sm font-medium">Existing Profiles</h4>
					{profiles.length === 0 ? (
						<p className="text-sm text-muted-foreground">
							No profiles created yet.
						</p>
					) : (
						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							{profiles.map((profile) => (
								<div
									key={profile.id}
									className={cn(
										"relative group overflow-hidden rounded-xl border bg-card text-card-foreground shadow transition-all hover:shadow-md",
										editingProfileId === profile.id && "ring-2 ring-primary",
									)}
								>
									<div className="p-6 space-y-4">
										<div className="flex items-start justify-between">
											<div>
												<h3 className="font-semibold leading-none tracking-tight">
													{profile.name}
												</h3>
												<p
													className="text-sm text-muted-foreground mt-1 truncate max-w-[200px]"
													title={profile.apprise_url}
												>
													{profile.apprise_url}
												</p>
											</div>
											<div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
												<Button
													variant="ghost"
													size="icon"
													className="h-8 w-8"
													onClick={() => handleTest(profile.apprise_url)}
													title="Send Test Notification"
													disabled={testProfileMutation.isPending}
												>
													<Send className="h-4 w-4" />
												</Button>
												<Button
													variant="ghost"
													size="icon"
													className="h-8 w-8"
													onClick={() => handleEdit(profile)}
												>
													<Edit2 className="h-4 w-4" />
												</Button>
												<Button
													variant="ghost"
													size="icon"
													className="h-8 w-8 text-destructive hover:text-destructive"
													onClick={() => handleDelete(profile.id)}
												>
													<Trash2 className="h-4 w-4" />
												</Button>
											</div>
										</div>

										<div className="grid grid-cols-2 gap-4 text-sm">
											<div className="flex items-center gap-2">
												<Clock className="h-4 w-4 text-muted-foreground" />
												<span>{profile.check_interval_minutes}m refresh</span>
											</div>
											<div className="flex items-center gap-2">
												<TrendingDown className="h-4 w-4 text-muted-foreground" />
												<span>
													{profile.price_drop_threshold_percent}% drop
												</span>
											</div>
										</div>

										<div className="flex flex-wrap gap-2 pt-2">
											{profile.notify_on_price_drop && (
												<span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">
													<DollarSign className="mr-1 h-3 w-3" /> Price Drop
												</span>
											)}
											{profile.notify_on_target_price && (
												<span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">
													<CheckCircle2 className="mr-1 h-3 w-3" /> Target Hit
												</span>
											)}
										</div>
									</div>
								</div>
							))}
						</div>
					)}
				</div>
			</CardContent>
		</Card>
	);
}
