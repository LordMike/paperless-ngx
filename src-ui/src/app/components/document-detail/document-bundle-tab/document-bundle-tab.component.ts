import {
  Component,
  EventEmitter,
  inject,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  Output,
} from '@angular/core'
import { FormsModule } from '@angular/forms'
import { RouterModule } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject } from 'rxjs'
import { first, takeUntil } from 'rxjs/operators'
import { Document } from 'src/app/data/document'
import { DocumentBundle } from 'src/app/data/document-bundle'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentBundleService } from 'src/app/services/rest/document-bundle.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../../common/confirm-dialog/confirm-dialog.component'
import { DocumentBundleEditDialogComponent } from '../../document-bundle-edit-dialog/document-bundle-edit-dialog.component'

@Component({
  selector: 'pngx-document-bundle-tab',
  templateUrl: './document-bundle-tab.component.html',
  imports: [FormsModule, RouterModule, NgxBootstrapIconsModule, CustomDatePipe],
})
export class DocumentBundleTabComponent
  implements OnInit, OnChanges, OnDestroy
{
  private documentBundleService = inject(DocumentBundleService)
  private modalService = inject(NgbModal)
  private toastService = inject(ToastService)
  private unsubscribeNotifier: Subject<void> = new Subject()

  @Input() document: Document
  @Input() documentId: number
  @Input() userCanEdit = false
  @Output() bundleChanged = new EventEmitter<void>()

  bundles: DocumentBundle[] = []
  selectedBundleId: number | null
  bundleItemName = ''
  bundleItemRelationship = ''
  bundleItemNameOriginal = ''
  bundleItemRelationshipOriginal = ''
  bundleMembershipSaving = false

  get bundleMembershipDirty(): boolean {
    return (
      this.bundleItemName !== this.bundleItemNameOriginal ||
      this.bundleItemRelationship !== this.bundleItemRelationshipOriginal
    )
  }

  ngOnInit(): void {
    this.loadBundles()
  }

  ngOnChanges(): void {
    this.syncFromDocument()
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next()
    this.unsubscribeNotifier.complete()
  }

  getBundleLabel(
    bundle: DocumentBundle | { name?: string; bundle_id?: string }
  ) {
    return bundle?.name || bundle?.bundle_id
  }

  getBundleOptionLabel(
    bundle: DocumentBundle | { name?: string; bundle_id?: string }
  ) {
    return bundle?.name
      ? `${bundle.name} (${bundle.bundle_id})`
      : bundle?.bundle_id
  }

  onBundleSelectionChange(bundleId: number | null) {
    if (!this.document) {
      this.selectedBundleId = this.document?.bundle?.id ?? null
      return
    }
    if (!bundleId) {
      if (this.document.bundle) {
        this.confirmRemoveFromBundle()
      } else {
        this.selectedBundleId = null
      }
      return
    }
    if (this.document.bundle) {
      if (bundleId === this.document.bundle.id) return
      this.confirmMoveToBundle(bundleId)
      return
    }
    this.addToBundle(bundleId)
  }

  saveCurrentBundleMembership() {
    if (
      !this.document?.bundle ||
      !this.bundleMembershipDirty ||
      this.bundleMembershipSaving
    )
      return
    this.bundleMembershipSaving = true
    this.documentBundleService
      .updateMembership(
        this.document.bundle.id,
        this.document.bundle.current_membership_id,
        this.bundleItemName,
        this.bundleItemRelationship
      )
      .pipe(first())
      .subscribe({
        next: () => {
          this.bundleItemNameOriginal = this.bundleItemName
          this.bundleItemRelationshipOriginal = this.bundleItemRelationship
          this.bundleMembershipSaving = false
          this.bundleChanged.emit()
        },
        error: (error) => {
          this.bundleMembershipSaving = false
          this.toastService.showError($localize`Error updating bundle`, error)
        },
      })
  }

  discardBundleMembershipChanges() {
    this.bundleItemName = this.bundleItemNameOriginal
    this.bundleItemRelationship = this.bundleItemRelationshipOriginal
  }

  createBundleForCurrentDocument() {
    this.documentBundleService
      .suggestId()
      .pipe(first())
      .subscribe({
        next: ({ bundle_id }) => this.openCreateBundleDialog(bundle_id),
        error: () => this.openCreateBundleDialog(''),
      })
  }

  private syncFromDocument() {
    this.selectedBundleId = this.document?.bundle?.id ?? null
    this.bundleItemName = this.document?.bundle?.current_bundle_item_name ?? ''
    this.bundleItemRelationship =
      this.document?.bundle?.current_bundle_item_relationship ?? ''
    this.bundleItemNameOriginal = this.bundleItemName
    this.bundleItemRelationshipOriginal = this.bundleItemRelationship
  }

  private confirmMoveToBundle(bundleId: number) {
    const targetBundle = this.bundles.find((bundle) => bundle.id === bundleId)
    if (!targetBundle || !this.document?.bundle) {
      this.selectedBundleId = this.document?.bundle?.id ?? null
      return
    }
    const sourceBundle = this.document.bundle
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    let confirmed = false
    modal.componentInstance.title = $localize`Move document`
    modal.componentInstance.message = $localize`Move this document from bundle <strong>${this.escapeHtml(this.getBundleLabel(sourceBundle))}</strong> to bundle <strong>${this.escapeHtml(this.getBundleLabel(targetBundle))}</strong>?`
    modal.componentInstance.btnCaption = $localize`Move`
    modal.componentInstance.confirmClicked.subscribe(() => {
      confirmed = true
      modal.componentInstance.buttonsEnabled = false
      this.documentBundleService
        .moveDocument(
          targetBundle.id,
          sourceBundle.current_membership_id,
          sourceBundle.current_bundle_item_name,
          sourceBundle.current_bundle_item_relationship
        )
        .pipe(first())
        .subscribe({
          next: () => {
            modal.close()
            this.loadBundles()
            this.bundleChanged.emit()
          },
          error: (error) => {
            modal.componentInstance.buttonsEnabled = true
            this.selectedBundleId = sourceBundle.id
            this.toastService.showError($localize`Error moving document`, error)
          },
        })
    })
    modal.result.then(() => {
      if (!confirmed) this.selectedBundleId = sourceBundle.id
    })
  }

  private confirmRemoveFromBundle() {
    if (!this.document?.bundle) return
    const sourceBundle = this.document.bundle
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    let confirmed = false
    modal.componentInstance.title = $localize`Remove from bundle`
    modal.componentInstance.message = $localize`Remove this document from bundle <strong>${this.escapeHtml(this.getBundleLabel(sourceBundle))}</strong>?`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Remove`
    modal.componentInstance.confirmClicked.subscribe(() => {
      confirmed = true
      modal.componentInstance.buttonsEnabled = false
      this.removeFromBundle({
        next: () => modal.close(),
        error: () => (modal.componentInstance.buttonsEnabled = true),
      })
    })
    modal.result.then(() => {
      if (!confirmed) this.selectedBundleId = sourceBundle.id
    })
  }

  private removeFromBundle(callbacks?: {
    next?: () => void
    error?: () => void
  }) {
    if (!this.document?.bundle) return
    this.documentBundleService
      .removeMembership(
        this.document.bundle.id,
        this.document.bundle.current_membership_id
      )
      .pipe(first())
      .subscribe({
        next: () => {
          this.loadBundles()
          this.bundleChanged.emit()
          callbacks?.next?.()
        },
        error: (error) => {
          this.selectedBundleId = this.document?.bundle?.id ?? null
          callbacks?.error?.()
          this.toastService.showError($localize`Error updating bundle`, error)
        },
      })
  }

  private addToBundle(bundleId: number) {
    if (!this.document) return
    this.documentBundleService
      .addDocument(bundleId, this.documentId)
      .pipe(first())
      .subscribe({
        next: () => {
          this.loadBundles()
          this.bundleChanged.emit()
        },
        error: (error) => {
          this.selectedBundleId = this.document?.bundle?.id ?? null
          this.toastService.showError($localize`Error updating bundle`, error)
        },
      })
  }

  private openCreateBundleDialog(bundleId: string) {
    if (!this.document) return
    const modal = this.modalService.open(DocumentBundleEditDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.mode = 'create'
    modal.componentInstance.bundle = {
      name: '',
      bundle_id: bundleId,
    } as DocumentBundle
    modal.componentInstance.saved.subscribe(({ name, bundle_id }) => {
      modal.componentInstance.networkActive = true
      modal.componentInstance.error = null
      this.documentBundleService
        .createForDocument(this.documentId, bundle_id, name)
        .pipe(first())
        .subscribe({
          next: () => {
            modal.close()
            this.loadBundles()
            this.bundleChanged.emit()
          },
          error: (error) => {
            modal.componentInstance.networkActive = false
            modal.componentInstance.error = error?.error ?? error
            this.toastService.showError($localize`Error creating bundle`, error)
          },
        })
    })
  }

  private escapeHtml(value: string): string {
    const element = document.createElement('div')
    element.innerText = value ?? ''
    return element.innerHTML
  }

  private loadBundles() {
    this.documentBundleService
      .listAll('bundle_id')
      .pipe(first(), takeUntil(this.unsubscribeNotifier))
      .subscribe({
        next: (result) => (this.bundles = result.results),
        error: (error) =>
          this.toastService.showError($localize`Error loading bundles`, error),
      })
  }
}
