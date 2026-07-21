# Desktop Setup Reference

## Quick Commands

```powershell
# Full setup from project root
.\setup_desktop.ps1

# Or from desktop folder
cd desktop
npm install
npm run build
npm run verify:bundle

# Install Tauri CLI globally
npm install -g @tauri-apps/cli
```

## Development

```powershell
# Option 1: Single command (spawns backend + frontend)
npx tauri dev

# Option 2: Split terminals (better for debugging)
# Terminal 1:
uvicorn igris.server:app --port 8765 --reload

# Terminal 2:
npm run dev
```

## Building Release

```powershell
# Generate icons first (one-time)
npx tauri icon path/to/1024x1024.png

# Build installer (MSI/NSIS)
npx tauri build
# Output: src-tauri/target/release/bundle/
```

## Testing

```powershell
# Frontend unit tests
npx vitest run

# Production bundle verification
npm run verify:bundle
```

## Project Structure

```
desktop/
├── src/
│   ├── components/       # React components
│   ├── lib/             # Shared utilities (api.ts, types.ts)
│   ├── App.tsx          # Main app
│   └── main.tsx         # Entry point
├── src-tauri/
│   ├── src/main.rs      # Tauri entry point (spawns Python backend)
│   └── tauri.conf.json  # Tauri config
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## Key Files

| File | Purpose |
|------|---------|
| `desktop/setup_desktop.ps1` | Full desktop setup script |
| `desktop/npm run verify:bundle` | Verifies production build works |
| `desktop/npx tauri dev` | Dev mode (Vite + backend) |
| `desktop/npx tauri build` | Release build |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `IGRIS_BACKEND_PORT` | 8765 | Backend port for frontend to connect |
| `IGRIS_BACKEND_HOST` | localhost | Backend host |

## Troubleshooting

**Backend connection failed**: Ensure `uvicorn igris.server:app --port 8765` is running

**Tauri build fails**: Run `rustup update` and `cargo clean` then retry

**npm install errors**: Delete `node_modules` and `package-lock.json`, then `npm install`