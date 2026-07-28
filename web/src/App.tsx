import { Shell } from "./components/Shell";
import { StoreProvider } from "./store";

export function App() {
  return (
    <StoreProvider>
      <Shell />
    </StoreProvider>
  );
}
