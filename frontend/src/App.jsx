import { Route, Routes } from "react-router-dom";
import Shell from "./components/Shell";
import Dashboard from "./pages/Dashboard";
import Inbox from "./pages/Inbox";
import Models from "./pages/Models";
import Search from "./pages/Search";
import TicketDetail from "./pages/TicketDetail";

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Dashboard />} />
        <Route path="inbox" element={<Inbox />} />
        <Route path="tickets/:id" element={<TicketDetail />} />
        <Route path="search" element={<Search />} />
        <Route path="models" element={<Models />} />
        <Route path="*" element={<Dashboard />} />
      </Route>
    </Routes>
  );
}
