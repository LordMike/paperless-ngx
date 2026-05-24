import { ObjectWithId } from './object-with-id'

export interface DocumentBundleItem extends ObjectWithId {
  document: number
  document_title?: string
  order_id: number
  bundle_item_name: string
  bundle_item_relationship?: string
  created?: string
}

export interface DocumentBundle extends ObjectWithId {
  name?: string
  bundle_id?: string
  created?: string
  document_count?: number
  items?: DocumentBundleItem[]
  documents?: number[]
  create_items?: {
    document: number
    bundle_item_name?: string
    bundle_item_relationship?: string
  }[]
}

export interface DocumentBundleDocumentSummary {
  membership_id: number
  document: number
  order_id: number
  bundle_item_name: string
  bundle_item_relationship?: string
  created?: string
  title: string
}

export interface DocumentBundleSummary {
  id: number
  name?: string
  bundle_id: string
  current_membership_id: number
  current_order_id: number
  current_bundle_item_name: string
  current_bundle_item_relationship?: string
  current_membership_created?: string
  items: DocumentBundleDocumentSummary[]
}
