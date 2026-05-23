import { Component, EventEmitter, Input, Output, inject } from '@angular/core'
import {
  FormControl,
  FormGroup,
  FormsModule,
  ReactiveFormsModule,
} from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DocumentBundle } from 'src/app/data/document-bundle'

@Component({
  selector: 'pngx-document-bundle-edit-dialog',
  templateUrl: './document-bundle-edit-dialog.component.html',
  imports: [FormsModule, ReactiveFormsModule],
})
export class DocumentBundleEditDialogComponent {
  private readonly activeModal = inject(NgbActiveModal)

  @Input()
  bundle: DocumentBundle

  @Input()
  mode: 'create' | 'edit' = 'edit'

  @Output()
  saved = new EventEmitter<{ name: string; bundle_id: string }>()

  closeEnabled = false
  networkActive = false
  error: any

  bundleForm = new FormGroup({
    name: new FormControl(''),
    bundle_id: new FormControl(''),
  })

  ngOnInit(): void {
    this.bundleForm.patchValue({
      name: this.bundle?.name ?? '',
      bundle_id: this.bundle?.bundle_id ?? '',
    })
    setTimeout(() => {
      this.closeEnabled = true
    })
  }

  save(): void {
    this.saved.emit({
      name: this.bundleForm.value.name ?? '',
      bundle_id: this.bundleForm.value.bundle_id ?? '',
    })
  }

  getBundleIdError(): string {
    const error = this.error?.bundle_id
    return Array.isArray(error) ? error.join(' ') : error
  }

  getFormError(): string {
    const error =
      this.error?.non_field_errors ||
      this.error?.documents ||
      this.error?.detail ||
      this.error?.error ||
      (typeof this.error === 'string' ? this.error : null)
    return Array.isArray(error) ? error.join(' ') : error
  }

  close(): void {
    this.activeModal.close()
  }
}
