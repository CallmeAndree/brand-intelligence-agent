import { redirect } from "next/navigation";

// Tab mặc định = Monitor. Trang gốc "/" điều hướng sang /monitor; Dashboard ở /dashboard.
export default function HomePage() {
  redirect("/monitor");
}
