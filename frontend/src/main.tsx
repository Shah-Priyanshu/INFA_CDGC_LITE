import React from 'react'
import ReactDOM from 'react-dom/client'
import { CssBaseline, Container, Typography, Box, Button, Tabs, Tab, TextField, List, ListItem, ListItemText, Divider, Stack } from '@mui/material'

function Health() {
  const [status, setStatus] = React.useState('unknown')
  const checkHealth = async () => {
    try {
      const r = await fetch('http://localhost:8000/healthz')
      const j = await r.json()
      setStatus(j.status)
    } catch (e) {
      setStatus('error')
    }
  }
  return (
    <Box>
      <Button variant="contained" onClick={checkHealth}>Check API Health</Button>
      <Typography sx={{ mt: 2 }}>API status: {status}</Typography>
    </Box>
  )
}

function Search() {
  const [q, setQ] = React.useState('')
  const [results, setResults] = React.useState<{assets:any[]; columns:any[]}>({assets:[], columns:[]})
  const [loading, setLoading] = React.useState(false)
  const onSearch = async () => {
    if (!q) return
    setLoading(true)
    try {
      const r = await fetch(`http://localhost:8000/search/?q=${encodeURIComponent(q)}`)
      const j = await r.json()
      setResults(j)
    } finally {
      setLoading(false)
    }
  }
  return (
    <Box>
      <Stack direction="row" spacing={2} alignItems="center">
        <TextField
          label="Search"
          size="small"
          value={q}
          onChange={(e: React.ChangeEvent<HTMLInputElement>)=>setQ(e.target.value)}
          onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>)=>{ if(e.key==='Enter') onSearch() }}
        />
        <Button variant="contained" onClick={onSearch} disabled={loading}>Search</Button>
      </Stack>
      <Typography variant="h6" sx={{ mt: 3 }}>Assets</Typography>
      <List dense>
        {results.assets.map((a: any, i: number)=> (
          <ListItem key={`a-${i}`}>
            <ListItemText
              primary={`${a.name} (system ${a.system_id})`}
              secondary={(a.highlight || '').toString().replace(/<[^>]+>/g, '') + (a.rank!==undefined?` | rank: ${a.rank.toFixed? a.rank.toFixed(3): a.rank}`:'')}
            />
          </ListItem>
        ))}
      </List>
      <Typography variant="h6" sx={{ mt: 2 }}>Columns</Typography>
      <List dense>
        {results.columns.map((c: any, i: number)=> (
          <ListItem key={`c-${i}`}>
            <ListItemText
              primary={`${c.name} (asset ${c.asset_id})`}
              secondary={(c.highlight || '').toString().replace(/<[^>]+>/g, '') + (c.rank!==undefined?` | rank: ${c.rank.toFixed? c.rank.toFixed(3): c.rank}`:'')}
            />
          </ListItem>
        ))}
      </List>
    </Box>
  )
}

function Lineage() {
  const [assetId, setAssetId] = React.useState('')
  const [nodes, setNodes] = React.useState<any[]>([])
  const [edges, setEdges] = React.useState<any[]>([])
  const [loading, setLoading] = React.useState(false)
  const load = async () => {
    setLoading(true)
    try {
      const qs = new URLSearchParams({ format: 'ui', depth: '2', ...(assetId? {asset_id: assetId}: {}) })
      const r = await fetch(`http://localhost:8000/lineage/graph?${qs.toString()}`)
      const j = await r.json()
      setNodes(j.nodes || [])
      setEdges(j.edges || [])
    } finally {
      setLoading(false)
    }
  }
  return (
    <Box>
      <Stack direction="row" spacing={2} alignItems="center">
        <TextField label="Asset ID (optional)" size="small" value={assetId} onChange={(e: React.ChangeEvent<HTMLInputElement>)=>setAssetId(e.target.value)} />
        <Button variant="contained" onClick={load} disabled={loading}>Load Graph</Button>
      </Stack>
      <Typography variant="h6" sx={{ mt: 2 }}>Nodes</Typography>
      <List dense>
        {nodes.map((n: any, i: number)=> (
          <ListItem key={`n-${i}`}>
            <ListItemText primary={`${n.id}: ${n.name}`} secondary={`system: ${n.system_id}`} />
          </ListItem>
        ))}
      </List>
      <Typography variant="h6" sx={{ mt: 2 }}>Edges</Typography>
      <List dense>
        {edges.map((e: any, i: number)=> (
          <ListItem key={`e-${i}`}>
            <ListItemText primary={`${e.source} -> ${e.target}`} />
          </ListItem>
        ))}
      </List>
    </Box>
  )
}

function App() {
  const [tab, setTab] = React.useState(0)
  return (
    <>
      <CssBaseline />
      <Container maxWidth="md">
        <Box sx={{ my: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom>
            CDGC-Lite UI
          </Typography>
          <Tabs value={tab} onChange={(_e: React.SyntheticEvent, v: number)=>setTab(v)} sx={{ mb: 2 }}>
            <Tab label="Health" />
            <Tab label="Search" />
            <Tab label="Lineage" />
          </Tabs>
          {tab===0 && <Health />}
          {tab===1 && <Search />}
          {tab===2 && <Lineage />}
        </Box>
      </Container>
    </>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
