import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import Step1Triage from "./pages/Step1Triage";
import BinAttack from "./pages/BinAttack";
import IpRepetition from "./pages/IpRepetition";
import MerchantBlacklist from "./pages/MerchantBlacklist";
import OverlaySimulator from "./pages/OverlaySimulator";
import AlertQueue from "./pages/AlertQueue";
import BusinessSummary from "./pages/BusinessSummary";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="step1" element={<Step1Triage />} />
        <Route path="overlay" element={<OverlaySimulator />} />
        <Route path="bin-attack" element={<BinAttack />} />
        <Route path="ip-repetition" element={<IpRepetition />} />
        <Route path="merchants" element={<MerchantBlacklist />} />
        <Route path="queue" element={<AlertQueue />} />
        <Route path="summary" element={<BusinessSummary />} />
      </Route>
    </Routes>
  );
}
