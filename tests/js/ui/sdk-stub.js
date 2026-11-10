import React from 'react'
const h = React.createElement
const cache = new Map()
export function resetQueries() { cache.clear() }
export async function settleQueries() { await Promise.all([...cache.values()].map(q => q.promise)) }
export function useQuery({ queryKey, queryFn, enabled = true }) {
  const key = JSON.stringify(queryKey)
  if (!enabled) return { data: undefined, isLoading: false, refetch: async () => {} }
  if (!cache.has(key)) {
    const query = { data: undefined, error: null, isLoading: true }
    query.promise = Promise.resolve().then(queryFn).then(data => { query.data = data; query.isLoading = false }, error => { query.error = error; query.isLoading = false })
    cache.set(key, query)
  }
  return { ...cache.get(key), refetch: async () => {}, dataUpdatedAt: 1 }
}
export function Button({ variant, size, asChild, loading, ...props }) { return h('button', props) }
export function Badge({ variant, size, ...props }) { return h('span', props) }
export function Codicon({ name, ...props }) { return h('span', { ...props, 'data-icon': name }) }
export function CopyButton({ text, label = 'Copy', ...props }) { return h('button', { type: 'button', 'data-copy': text }, label) }
export function Dialog({ open, children }) { return open ? h(React.Fragment, null, children) : null }
export function DialogContent({ children, onOpenAutoFocus, onCloseAutoFocus, bodyClassName, showCloseButton, ...props }) { return h('div', { role: 'dialog', 'aria-modal': true, ...props }, children) }
export const DialogHeader = ({ children, ...props }) => h('header', props, children)
export const DialogFooter = ({ children }) => h('footer', null, children)
export const DialogTitle = ({ children }) => h('h2', null, children)
export const DialogDescription = ({ children, ...props }) => h('p', props, children)
export const Tabs = ({ children, className }) => h('div', { className }, children)
export const TabsList = ({ children, ...props }) => h('div', { role: 'tablist', ...props }, children)
export const TabsTrigger = ({ children, value, ...props }) => h('button', { role: 'tab', ...props }, children)
export const DropdownMenu = ({ children }) => h('div', null, children)
export const DropdownMenuTrigger = ({ children }) => h(React.Fragment, null, children)
export const DropdownMenuContent = () => null
export const DropdownMenuItem = ({ children }) => h('div', null, children)
export const DropdownMenuSeparator = () => h('hr')
export const Tip = ({ children }) => children
export const Skeleton = props => h('div', { ...props, 'data-skeleton': true })
export const EmptyState = ({ title, description }) => h('div', null, h('h2', null, title), h('p', null, description))
export const ErrorState = ({ title, description, children }) => h('div', { role: 'alert' }, h('h2', null, title), h('p', null, description), children)
export const SearchField = ({ value, onChange, placeholder, 'aria-label': label }) => h('input', { value, onChange, placeholder, 'aria-label': label })
export const SegmentedControl = ({ options, value, onChange }) => h('div', null, options.map(o => h('button', { key: o.id, 'aria-pressed': o.id === value, onClick: () => onChange(o.id) }, o.label)))
export const host = { navigate() {}, state: { connectionId: { get: () => 'demo-backend' }, profile: { get: () => 'demo-profile' } } }
export const useValue = atom => atom.get()
export const relativeTime = milliseconds => `relative ${milliseconds}`
export const fmtDateTime = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' })
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export const TRANSCRIPT_DIRECTIVE_AREA = 'transcript.directive'
