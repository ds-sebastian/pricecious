import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Menu } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Nav } from "./Nav";
import { ThemeToggle } from "./ThemeToggle";

const Layout = ({ children, theme, toggleTheme }) => {
	const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

	return (
		<div className="min-h-screen bg-background font-sans antialiased">
			{/* Sidebar */}
			<aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r bg-card hidden md:block">
				<div className="flex h-full flex-col">
					<div className="flex h-14 items-center border-b px-6">
						<Link to="/" className="flex items-center gap-2 font-semibold">
							<img src="/logo.png" alt="Pricecious Logo" className="h-8 w-8" />
							<span className="text-xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
								Pricecious
							</span>
						</Link>
					</div>
					<Nav />
					<div className="border-t p-4">
						<ThemeToggle
							theme={theme}
							toggleTheme={toggleTheme}
							showLabel
							className="w-full px-4"
						/>
					</div>
				</div>
			</aside>

			{/* Mobile Header */}
			<header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b bg-background px-6 md:hidden">
				<Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
					<SheetTrigger asChild>
						<Button variant="ghost" size="icon">
							<Menu className="h-5 w-5" />
						</Button>
					</SheetTrigger>
					<SheetContent side="left" className="w-64 p-0">
						<div className="flex h-full flex-col">
							<div className="flex h-14 items-center border-b px-6">
								<img
									src="/logo.png"
									alt="Pricecious Logo"
									className="h-8 w-8 mr-2"
								/>
								<span className="text-xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
									Pricecious
								</span>
							</div>
							<Nav onItemClick={() => setMobileMenuOpen(false)} />
							<div className="border-t p-4">
								<ThemeToggle
									theme={theme}
									toggleTheme={toggleTheme}
									showLabel
									className="w-full"
								/>
							</div>
						</div>
					</SheetContent>
				</Sheet>
				<Link to="/" className="flex items-center gap-2 font-semibold">
					<img src="/logo.png" alt="Pricecious Logo" className="h-6 w-6" />
					Pricecious
				</Link>
				<div className="ml-auto flex items-center gap-2">
					<ThemeToggle theme={theme} toggleTheme={toggleTheme} />
				</div>
			</header>

			{/* Main Content */}
			<main className="flex-1 md:pl-64">
				<div className="container py-6">{children}</div>
			</main>
		</div>
	);
};

export default Layout;
