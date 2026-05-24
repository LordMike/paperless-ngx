import { Component, Input } from '@angular/core'
import { RouterModule } from '@angular/router'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Document } from 'src/app/data/document'

@Component({
  selector: 'pngx-document-bundle-menu',
  templateUrl: './document-bundle-menu.component.html',
  imports: [NgbDropdownModule, NgxBootstrapIconsModule, RouterModule],
})
export class DocumentBundleMenuComponent {
  @Input() document: Document
  @Input() documentId: number
}
