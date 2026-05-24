import { Injectable } from '@angular/core'
import { Observable } from 'rxjs'
import {
  DocumentBundle,
  DocumentBundleItem,
} from 'src/app/data/document-bundle'
import { AbstractPaperlessService } from './abstract-paperless-service'

@Injectable({
  providedIn: 'root',
})
export class DocumentBundleService extends AbstractPaperlessService<DocumentBundle> {
  constructor() {
    super()
    this.resourceName = 'bundles'
  }

  createFromDocuments(
    documentIds: number[],
    bundleId?: string,
    name?: string
  ): Observable<DocumentBundle> {
    this.clearCache()
    const body: { documents: number[]; bundle_id?: string; name?: string } = {
      documents: documentIds,
    }
    if (bundleId !== undefined) body.bundle_id = bundleId
    if (name !== undefined) body.name = name
    return this.http.post<DocumentBundle>(this.getResourceUrl(), body)
  }

  suggestId(): Observable<{ bundle_id: string }> {
    return this.http.get<{ bundle_id: string }>(
      this.getResourceUrl(null, 'suggest_id')
    )
  }

  createForDocument(
    documentId: number,
    bundleId?: string,
    name?: string
  ): Observable<DocumentBundle> {
    this.clearCache()
    const body: { document: number; bundle_id?: string; name?: string } = {
      document: documentId,
    }
    if (bundleId !== undefined) body.bundle_id = bundleId
    if (name !== undefined) body.name = name
    return this.http.post<DocumentBundle>(
      this.getResourceUrl(null, 'create_for_document'),
      body
    )
  }

  addDocument(
    bundleId: number,
    documentId: number,
    bundleItemName?: string
  ): Observable<DocumentBundleItem> {
    this.clearCache()
    return this.http.post<DocumentBundleItem>(
      this.getResourceUrl(bundleId, 'documents'),
      {
        document: documentId,
        bundle_item_name: bundleItemName,
      }
    )
  }

  updateMembership(
    bundleId: number,
    membershipId: number,
    bundleItemName: string,
    bundleItemRelationship?: string
  ): Observable<DocumentBundleItem> {
    this.clearCache()
    return this.http.patch<DocumentBundleItem>(
      `${this.getResourceUrl(bundleId, 'documents')}${membershipId}/`,
      {
        bundle_item_name: bundleItemName,
        bundle_item_relationship: bundleItemRelationship ?? '',
      }
    )
  }

  removeMembership(bundleId: number, membershipId: number): Observable<void> {
    this.clearCache()
    return this.http.delete<void>(
      `${this.getResourceUrl(bundleId, 'documents')}${membershipId}/`
    )
  }

  moveDocument(
    targetBundleId: number,
    membershipId: number,
    bundleItemName?: string,
    bundleItemRelationship?: string
  ): Observable<DocumentBundleItem> {
    this.clearCache()
    return this.http.post<DocumentBundleItem>(
      this.getResourceUrl(targetBundleId, 'move_document'),
      {
        membership: membershipId,
        bundle_item_name: bundleItemName,
        bundle_item_relationship: bundleItemRelationship ?? '',
      }
    )
  }

  reorder(
    bundleId: number,
    membershipIds: number[]
  ): Observable<DocumentBundle> {
    this.clearCache()
    return this.http.patch<DocumentBundle>(
      this.getResourceUrl(bundleId, 'order'),
      {
        membership_ids: membershipIds,
      }
    )
  }
}
