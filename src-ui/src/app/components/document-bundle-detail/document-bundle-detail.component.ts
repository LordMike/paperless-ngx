import {
  CdkDragDrop,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { Component, inject, OnInit } from '@angular/core'
import { ActivatedRoute, Router, RouterModule } from '@angular/router'
import { NgbModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  DocumentBundle,
  DocumentBundleItem,
} from 'src/app/data/document-bundle'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentBundleService } from 'src/app/services/rest/document-bundle.service'
import { ToastService } from 'src/app/services/toast.service'
import { ConfirmDialogComponent } from '../common/confirm-dialog/confirm-dialog.component'
import { PageHeaderComponent } from '../common/page-header/page-header.component'
import { DocumentBundleItemEditDialogComponent } from '../document-bundle-item-edit-dialog/document-bundle-item-edit-dialog.component'

@Component({
  selector: 'pngx-document-bundle-detail',
  templateUrl: './document-bundle-detail.component.html',
  styleUrls: ['./document-bundle-detail.component.scss'],
  imports: [
    RouterModule,
    NgxBootstrapIconsModule,
    PageHeaderComponent,
    CustomDatePipe,
    DragDropModule,
  ],
})
export class DocumentBundleDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute)
  private readonly router = inject(Router)
  private readonly bundleService = inject(DocumentBundleService)
  private readonly toastService = inject(ToastService)
  private readonly modalService = inject(NgbModal)

  bundle: DocumentBundle
  orderSaving = false
  deleting = false
  removingMembership = false

  ngOnInit(): void {
    this.load()
  }

  load() {
    const id = +this.route.snapshot.paramMap.get('id')
    this.bundleService.get(id).subscribe({
      next: (bundle) => {
        this.bundle = bundle
      },
      error: (error) =>
        this.toastService.showError($localize`Error loading bundle`, error),
    })
  }

  editItem(item: DocumentBundleItem) {
    const modal = this.modalService.open(
      DocumentBundleItemEditDialogComponent,
      {
        backdrop: 'static',
      }
    )
    modal.componentInstance.item = item
    modal.componentInstance.saved.subscribe(
      ({
        bundle_item_name,
        bundle_item_type,
      }: {
        bundle_item_name: string
        bundle_item_type: string
      }) => {
        this.bundleService
          .updateMembership(
            this.bundle.id,
            item.id,
            bundle_item_name,
            bundle_item_type
          )
          .subscribe({
            next: () => {
              modal.close()
              this.load()
            },
            error: (error) =>
              this.toastService.showError(
                $localize`Error updating bundle`,
                error
              ),
          })
      }
    )
  }

  remove(item: DocumentBundleItem) {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Remove from bundle`
    modal.componentInstance.messageBold = $localize`Remove "${item.bundle_item_name}" from this bundle?`
    modal.componentInstance.message = $localize`The document will not be deleted. If this is the last document in the bundle, the empty bundle will be deleted.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Remove`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.removingMembership = true
      const wasLastItem = this.bundle.items.length <= 1
      this.bundleService.removeMembership(this.bundle.id, item.id).subscribe({
        next: () => {
          this.removingMembership = false
          modal.close()
          if (wasLastItem) {
            this.router.navigate(['attributes', 'bundles'])
          } else {
            this.load()
          }
        },
        error: (error) => {
          this.removingMembership = false
          modal.componentInstance.buttonsEnabled = true
          this.toastService.showError($localize`Error updating bundle`, error)
        },
      })
    })
  }

  drop(event: CdkDragDrop<DocumentBundleItem[]>) {
    if (!this.bundle?.items || event.previousIndex === event.currentIndex) {
      return
    }
    moveItemInArray(this.bundle.items, event.previousIndex, event.currentIndex)
    const membershipIds = this.bundle.items.map((item) => item.id)
    this.orderSaving = true
    this.bundleService.reorder(this.bundle.id, membershipIds).subscribe({
      next: () => {
        this.orderSaving = false
        this.load()
      },
      error: (error) => {
        this.orderSaving = false
        this.load()
        this.toastService.showError(
          $localize`Error updating bundle order`,
          error
        )
      },
    })
  }

  deleteBundle() {
    const modal = this.modalService.open(ConfirmDialogComponent, {
      backdrop: 'static',
    })
    modal.componentInstance.title = $localize`Delete bundle`
    modal.componentInstance.messageBold = $localize`Delete bundle "${this.bundle.bundle_id}"?`
    modal.componentInstance.message = $localize`Documents will not be deleted. Only the bundle and its document membership records will be removed.`
    modal.componentInstance.btnClass = 'btn-danger'
    modal.componentInstance.btnCaption = $localize`Delete`
    modal.componentInstance.confirmClicked.subscribe(() => {
      modal.componentInstance.buttonsEnabled = false
      this.deleting = true
      this.bundleService.delete(this.bundle).subscribe({
        next: () => {
          this.deleting = false
          modal.close()
          this.router.navigate(['attributes', 'bundles'])
        },
        error: (error) => {
          this.deleting = false
          modal.componentInstance.buttonsEnabled = true
          this.toastService.showError($localize`Error deleting bundle`, error)
        },
      })
    })
  }
}
