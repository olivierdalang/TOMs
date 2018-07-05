#-----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#---------------------------------------------------------------------
# Tim Hancock 2017

"""
Series of functions to deal with restrictionsInProposals. Defined as static functions to allow them to be used in forms ... (not sure if this is the best way ...)

"""
from PyQt4.QtGui import (
    QMessageBox,
    QAction,
    QIcon,
    QDialogButtonBox,
    QPixmap,
    QLabel, QDockWidget
)
from PyQt4.QtCore import (
    QObject, QTimer, pyqtSignal
)

from qgis.core import (
    QgsExpressionContextUtils,
    QgsExpression,
    QgsFeatureRequest,
    QgsMapLayerRegistry,
    QgsMessageLog, QgsFeature, QgsGeometry,
    QgsTransaction, QgsTransactionGroup
)

from qgis.gui import *
import functools
import time
import os

from TOMs.constants import (
    ACTION_CLOSE_RESTRICTION,
    ACTION_OPEN_RESTRICTION,
    PROPOSAL_STATUS_IN_PREPARATION,
    PROPOSAL_STATUS_ACCEPTED,
    PROPOSAL_STATUS_REJECTED
)

from generateGeometryUtils import generateGeometryUtils
#from TOMs.core.proposalsManager import *
from TOMs.core.proposalsManager import *

from abc import ABCMeta

import uuid

class TOMsTransaction (QObject):

    transactionCompleted = pyqtSignal()
    """Signal will be emitted, when the transaction is finished - either committed or rollback"""

    def __init__(self, iface, proposalsManager):

        QObject.__init__(self)

        self.iface = iface

        self.proposalsManager = proposalsManager  # included to allow call to updateMapCanvas

        #self.currTransactionGroup = None
        self.currTransactionGroup = QgsTransactionGroup()
        self.prepareLayerSet()

    def prepareLayerSet(self):

        # Function to create group of layers to be in Transaction for changing proposal

        self.tableNames = setupTableNames(self.iface)

        QgsMessageLog.logMessage("In TOMsTransaction. prepareLayerSet: ", tag="TOMs panel")

        idxRestrictionsLayerName = self.tableNames.RESTRICTIONLAYERS.fieldNameIndex("RestrictionLayerName")

        self.setTransactionGroup = [self.tableNames.PROPOSALS]
        self.setTransactionGroup.append(self.tableNames.RESTRICTIONS_IN_PROPOSALS)

        for layer in self.tableNames.RESTRICTIONLAYERS.getFeatures():

            currRestrictionLayerName = layer[idxRestrictionsLayerName]

            restrictionLayer = QgsMapLayerRegistry.instance().mapLayersByName(currRestrictionLayerName)[0]

            self.setTransactionGroup.append(restrictionLayer)
            QgsMessageLog.logMessage("In TOMsTransaction.prepareLayerSet. Adding " + str(restrictionLayer.name()), tag="TOMs panel")


    def createTransactionGroup(self):

        QgsMessageLog.logMessage("In TOMsTransaction.createTransactionGroup",
                                 tag="TOMs panel")

        """if self.currTransactionGroup:
            QgsMessageLog.logMessage("In createTransactionGroup. Transaction ALREADY exists",
                                    tag="TOMs panel")
            return"""

        if self.currTransactionGroup:

            for layer in self.setTransactionGroup:
                self.currTransactionGroup.addLayer(layer)
                QgsMessageLog.logMessage("In createTransactionGroup. Adding " + str(layer.name()), tag="TOMs panel")
                layer.beforeCommitChanges.connect(functools.partial(self.printMessage, layer, "beforeCommitChanges"))
                layer.layerModified.connect(functools.partial(self.printMessage, layer, "layerModified"))
                layer.editingStopped.connect(functools.partial(self.printMessage, layer, "editingStopped"))
                layer.attributeValueChanged.connect(self.printAttribChanged)
                layer.raiseError.connect(functools.partial(self.printRaiseError, layer))

                #layer.editCommandEnded.connect(functools.partial(self.printMessage, layer, "editCommandEnded"))

                #layer.editBuffer().committedAttributeValuesChanges.connect(functools.partial(self.layerCommittedAttributeValuesChanges, layer))

            #layer.startEditing() # edit layer is now active ...
            self.modified = False
            self.errorOccurred = False

            self.transactionCompleted.connect(self.proposalsManager.updateMapCanvas)

            return

    def startTransactionGroup(self):

        QgsMessageLog.logMessage("In startTransactionGroup.", tag="TOMs panel")

        if self.currTransactionGroup.isEmpty():
            QgsMessageLog.logMessage("In startTransactionGroup. Currently empty adding layers", tag="TOMs panel")
            self.createTransactionGroup()

        status = self.tableNames.PROPOSALS.startEditing()  # could be any table ...
        if status == False:
            QgsMessageLog.logMessage("In startTransactionGroup. *** Error starting transaction ...", tag="TOMs panel")

        return status

    def layerModified(self):
        self.modified = True

    def modified(self):
        # indicates whether or not there has been any change within the transaction
        return self.modified

    def printMessage(self, layer, message):
        QgsMessageLog.logMessage("In printMessage. " + str(message) + " ... " + str(layer.name()),
                                 tag="TOMs panel")

    def printAttribChanged(self, fid, idx, v):
        QgsMessageLog.logMessage("Attributes changed for feature " + str(fid),
                                 tag="TOMs panel")

    def printRaiseError(self, layer, message):
        QgsMessageLog.logMessage("Error from " + str(layer.name()) + ": " + str(message),
                                 tag="TOMs panel")
        self.errorOccurred = True
        self.errorMessage = message

    def commitTransactionGroup(self, currRestrictionLayer):

        QgsMessageLog.logMessage("In commitTransactionGroup",
                                 tag="TOMs panel")

        # unset map tool. I don't understand why this is required, but ... without it QGIS crashes
        self.iface.mapCanvas().unsetMapTool(self.iface.mapCanvas().mapTool())

        if not self.currTransactionGroup:
            QgsMessageLog.logMessage("In commitTransactionGroup. Transaction DOES NOT exist",
                                    tag="TOMs panel")
            return

        if self.errorOccurred == True:
            reply = QMessageBox.information(None, "Error",
                                            str(self.errorMessage), QMessageBox.Ok)
            self.rollBackTransactionGroup()
            return False

        # Now check to see that there has been a change in the "main" restriction layer
        if currRestrictionLayer:

            if currRestrictionLayer.editBuffer().isModified() == False:
                reply = QMessageBox.information(None, "Error",
                                                "Problem with saving " + str(currRestrictionLayer.name()),
                                                QMessageBox.Ok)
                self.rollBackTransactionGroup()
                return False

        QgsMessageLog.logMessage("In commitTransactionGroup. Committing transaction",
                                 tag="TOMs panel")

        #modifiedTransaction = self.currTransactionGroup.modified()

        """if self.modified == True:
            QgsMessageLog.logMessage("In commitTransactionGroup. Transaction has been changed ...",
                                     tag="TOMs panel")
        else:
            QgsMessageLog.logMessage("In commitTransactionGroup. Transaction has NOT been changed ...",
                                     tag="TOMs panel")"""

        #self.currTransactionGroup.commitError.connect(self.errorInTransaction)

        for layer in self.setTransactionGroup:

            QgsMessageLog.logMessage("In commitTransactionGroup. Considering: " + layer.name(),
                                     tag="TOMs panel")

            commitStatus = layer.commitChanges()
            #commitStatus = True  # for testing ...

            """try:
                #layer.commitChanges()
                QTimer.singleShot(0, layer.commitChanges())
                commitStatus = True
            except:
                #commitErrors = layer.commitErrors()
                commitStatus = False

                QgsMessageLog.logMessage("In commitTransactionGroup. error: " + str(layer.commitErrors()),
                                     tag="TOMs panel")"""

            if commitStatus == False:
                reply = QMessageBox.information(None, "Error",
                                                "Changes to " + layer.name() + " failed: " + str(
                                                    layer.commitErrors()), QMessageBox.Ok)
                commitErrors = layer.rollBack()

            break

        self.modified = False
        self.errorOccurred = False

        # signal for redraw ...
        self.transactionCompleted.emit()

        return commitStatus

    def layersInTransaction(self):
        return self.setTransactionGroup

    def errorInTransaction(self, errorMsg):
        reply = QMessageBox.information(None, "Error",
                                        "Proposal changes failed: " + errorMsg, QMessageBox.Ok)
        QgsMessageLog.logMessage("In errorInTransaction: " + errorMsg,
                                 tag="TOMs panel")

        #def __del__(self):
        #pass
      
    def deleteTransactionGroup(self):

        if self.currTransactionGroup:

            if self.currTransactionGroup.modified():
                QgsMessageLog.logMessage("In deleteTransactionGroup. Transaction contains edits ... NOT deleting",
                                        tag="TOMs panel")
                return

            self.currTransactionGroup.commitError.disconnect(self.errorInTransaction)
            self.currTransactionGroup = None

        pass

        return
      
    def rollBackTransactionGroup(self):

        QgsMessageLog.logMessage("In rollBackTransactionGroup",
                                 tag="TOMs panel")

        # unset map tool. I don't understand why this is required, but ... without it QGIS crashes
        self.iface.mapCanvas().unsetMapTool(self.iface.mapCanvas().mapTool())

        try:
            self.tableNames.PROPOSALS.rollBack()  # could be any table ...
        except:
            QgsMessageLog.logMessage("In rollBackTransactionGroup. error: ...",
                                     tag="TOMs panel")

        #self.iface.activeLayer().stopEditing()

        self.modified = False
        self.errorOccurred = False
        self.errorMessage = None

        return

class setupTableNames():
    def __init__(self, iface):

        self.iface = iface
        found = True

        #RestrictionsLayers = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionLayers")[0]

        if QgsMapLayerRegistry.instance().mapLayersByName("Proposals"):
            self.PROPOSALS = QgsMapLayerRegistry.instance().mapLayersByName("Proposals")[0]
        else:
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("Table Proposals is not present"))
            found = False

        if QgsMapLayerRegistry.instance().mapLayersByName("ProposalStatusTypes"):
            self.PROPOSAL_STATUS_TYPES = QgsMapLayerRegistry.instance().mapLayersByName("Proposals")[0]
        else:
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("Table ProposalStatusTypes is not present"))
            found = False

        if QgsMapLayerRegistry.instance().mapLayersByName("RestrictionLayers"):
            self.RESTRICTIONLAYERS = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionLayers")[0]
        else:
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("Table RestrictionLayers is not present"))
            found = False

        if QgsMapLayerRegistry.instance().mapLayersByName("RestrictionsInProposals"):
            self.RESTRICTIONS_IN_PROPOSALS = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionsInProposals")[0]
        else:
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("Table RestrictionsInProposals is not present"))
            found = False

        if QgsMapLayerRegistry.instance().mapLayersByName("Bays"):
            self.BAYS = QgsMapLayerRegistry.instance().mapLayersByName("Bays")[0]
        else:
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("Table Bays is not present"))
            found = False

        if QgsMapLayerRegistry.instance().mapLayersByName("Lines"):
            self.LINES = QgsMapLayerRegistry.instance().mapLayersByName("Lines")[0]
        else:
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("Table Lines is not present"))
            found = False

        if QgsMapLayerRegistry.instance().mapLayersByName("Signs"):
            self.SIGNS = QgsMapLayerRegistry.instance().mapLayersByName("Signs")[0]
        else:
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("Table Signs is not present"))
            found = False

        if QgsMapLayerRegistry.instance().mapLayersByName("RestrictionPolygons"):
            self.RESTRICTION_POLYGONS = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionPolygons")[0]
        else:
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("Table RestrictionPolygons is not present"))
            found = False

        if QgsMapLayerRegistry.instance().mapLayersByName("CPZs"):
            self.CPZs = QgsMapLayerRegistry.instance().mapLayersByName("CPZs")[0]
        else:
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("Table CPZs is not present"))
            found = False

        if QgsMapLayerRegistry.instance().mapLayersByName("ParkingTariffAreas"):
            self.PTAs = QgsMapLayerRegistry.instance().mapLayersByName("ParkingTariffAreas")[0]
        else:
            QMessageBox.information(self.iface.mainWindow(), "ERROR", ("Table ParkingTariffAreas is not present"))
            found = False

        # TODO: include the required lookup tables

        # TODO: need to deal with any errors arising ...

class TOMsLabels():
    def __init__(self, iface, proposalsManager):

        self.iface = iface
        self.proposalsManager = proposalsManager

    def afterUnPin(self, currRestriction, currRestrictionLayer):

        # The unpin action will populate the x,y values of the layer

        currProposalID = self.proposalsManager.currentProposal()

        currRestrictionLayerID = self.getRestrictionLayerTableID(currRestrictionLayer)

        idxRestrictionID = currRestriction.fieldNameIndex("RestrictionID")

        if self.restrictionInProposal(currRestriction[idxRestrictionID], currRestrictionLayerID, currProposalID):
            pass

    def afterMove(self):
        pass

    def afterRotate(self):
        pass


class RestrictionTypeUtilsMixin():

    def __init__(self, iface):
        #self.constants = TOMsConstants()
        #self.proposalsManager = proposalsManager
        self.iface = iface
        self.tableNames = setupTableNames(self.iface)
        #super().__init__()
        self.currTransaction = None
        #self.proposalTransaction = QgsTransaction()
        #self.proposalPanel = None

        pass

    def restrictionInProposal(self, currRestrictionID, currRestrictionLayerID, proposalID):
        # returns True if resstriction is in Proposal
        QgsMessageLog.logMessage("In restrictionInProposal.", tag="TOMs panel")

        RestrictionsInProposalsLayer = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionsInProposals")[0]

        restrictionFound = False

        # not sure if there is better way to search for something, .e.g., using SQL ??

        for restrictionInProposal in RestrictionsInProposalsLayer.getFeatures():
            if restrictionInProposal.attribute("RestrictionID") == currRestrictionID:
                if restrictionInProposal.attribute("RestrictionTableID") == currRestrictionLayerID:
                    if restrictionInProposal.attribute("ProposalID") == proposalID:
                        restrictionFound = True

        QgsMessageLog.logMessage("In restrictionInProposal. restrictionFound: " + str(restrictionFound),
                                 tag="TOMs panel")

        return restrictionFound

    def addRestrictionToProposal(self, restrictionID, restrictionLayerTableID, proposalID, proposedAction):
        # adds restriction to the "RestrictionsInProposals" layer
        QgsMessageLog.logMessage("In addRestrictionToProposal.", tag="TOMs panel")

        RestrictionsInProposalsLayer = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionsInProposals")[0]

        #RestrictionsInProposalsLayer.startEditing()

        idxProposalID = RestrictionsInProposalsLayer.fieldNameIndex("ProposalID")
        idxRestrictionID = RestrictionsInProposalsLayer.fieldNameIndex("RestrictionID")
        idxRestrictionTableID = RestrictionsInProposalsLayer.fieldNameIndex("RestrictionTableID")
        idxActionOnProposalAcceptance = RestrictionsInProposalsLayer.fieldNameIndex(
            "ActionOnProposalAcceptance")

        newRestrictionsInProposal = QgsFeature(RestrictionsInProposalsLayer.fields())
        newRestrictionsInProposal.setGeometry(QgsGeometry())

        newRestrictionsInProposal[idxProposalID] = proposalID
        newRestrictionsInProposal[idxRestrictionID] = restrictionID
        newRestrictionsInProposal[idxRestrictionTableID] = restrictionLayerTableID
        newRestrictionsInProposal[idxActionOnProposalAcceptance] = proposedAction

        QgsMessageLog.logMessage(
            "In addRestrictionToProposal. Before record create. RestrictionID: " + str(restrictionID),
            tag="TOMs panel")

        attrs = newRestrictionsInProposal.attributes()

        #QMessageBox.information(None, "Information", ("addRestrictionToProposal" + str(attrs)))

        returnStatus = RestrictionsInProposalsLayer.addFeatures([newRestrictionsInProposal])

        return returnStatus

    def getRestrictionsLayer(self, currRestrictionTableRecord):
        # return the layer given the row in "RestrictionLayers"
        QgsMessageLog.logMessage("In getRestrictionLayer.", tag="TOMs panel")

        RestrictionsLayers = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionLayers")[0]

        idxRestrictionsLayerName = RestrictionsLayers.fieldNameIndex("RestrictionLayerName")

        currRestrictionsTableName = currRestrictionTableRecord[idxRestrictionsLayerName]

        RestrictionLayer = QgsMapLayerRegistry.instance().mapLayersByName(currRestrictionsTableName)[0]

        return RestrictionLayer

    def getRestrictionsLayerFromID(self, currRestrictionTableID):
        # return the layer given the row in "RestrictionLayers"
        QgsMessageLog.logMessage("In getRestrictionsLayerFromID.", tag="TOMs panel")

        RestrictionsLayers = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionLayers")[0]

        idxRestrictionsLayerName = RestrictionsLayers.fieldNameIndex("RestrictionLayerName")
        idxRestrictionsLayerID = RestrictionsLayers.fieldNameIndex("id")

        for layer in RestrictionsLayers.getFeatures():
            if layer[idxRestrictionsLayerID] == currRestrictionTableID:
                currRestrictionLayerName = layer[idxRestrictionsLayerName]

        restrictionLayer = QgsMapLayerRegistry.instance().mapLayersByName(currRestrictionLayerName)[0]

        return restrictionLayer

    def getRestrictionLayerTableID(self, currRestLayer):
        QgsMessageLog.logMessage("In getRestrictionLayerTableID.", tag="TOMs panel")
        # find the ID for the layer within the table "

        RestrictionsLayers = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionLayers")[0]

        layersTableID = 0

        # not sure if there is better way to search for something, .e.g., using SQL ??

        for layer in RestrictionsLayers.getFeatures():
            if layer.attribute("RestrictionLayerName") == str(currRestLayer.name()):
                layersTableID = layer.attribute("id")

        QgsMessageLog.logMessage("In getRestrictionLayerTableID. layersTableID: " + str(layersTableID),
                                 tag="TOMs panel")

        return layersTableID

    def getRestrictionBasedOnRestrictionID(self, currRestrictionID, currRestrictionLayer):
        # return the layer given the row in "RestrictionLayers"
        QgsMessageLog.logMessage("In getRestriction.", tag="TOMs panel")

        #query2 = '"RestrictionID" = \'{restrictionid}\''.format(restrictionid=currRestrictionID)

        queryString = "\"RestrictionID\" = \'" + currRestrictionID + "\'"

        QgsMessageLog.logMessage("In getRestriction: queryString: " + str(queryString), tag="TOMs panel")

        expr = QgsExpression(queryString)

        for feature in currRestrictionLayer.getFeatures(QgsFeatureRequest(expr)):
            return feature

        QgsMessageLog.logMessage("In getRestriction: Restriction not found", tag="TOMs panel")
        return None


    def deleteRestrictionInProposal(self, currRestrictionID, currRestrictionLayerID, proposalID):
        QgsMessageLog.logMessage("In deleteRestrictionInProposal: " + str(currRestrictionID), tag="TOMs panel")

        returnStatus = False

        RestrictionsInProposalsLayer = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionsInProposals")[0]

        #RestrictionsInProposalsLayer.startEditing()

        for restrictionInProposal in RestrictionsInProposalsLayer.getFeatures():
            if restrictionInProposal.attribute("RestrictionID") == currRestrictionID:
                if restrictionInProposal.attribute("RestrictionTableID") == currRestrictionLayerID:
                    if restrictionInProposal.attribute("ProposalID") == proposalID:
                        QgsMessageLog.logMessage("In deleteRestrictionInProposal - deleting ",
                                                 tag="TOMs panel")

                        attrs = restrictionInProposal.attributes()

                        #QMessageBox.information(None, "Information", ("deleteRestrictionInProposal" + str(attrs)))

                        returnStatus = RestrictionsInProposalsLayer.deleteFeature(restrictionInProposal.id())
                        #returnStatus = True
                        return returnStatus

        return returnStatus

    def onSaveRestrictionDetails(self, currRestriction, currRestrictionLayer, dialog, restrictionTransaction):
        QgsMessageLog.logMessage("In onSaveRestrictionDetails: " + str(currRestriction.attribute("GeometryID")), tag="TOMs panel")

        #currRestrictionLayer.startEditing()

        currProposalID = int(QgsExpressionContextUtils.projectScope().variable('CurrentProposal'))

        if currProposalID > 0:

            currRestrictionLayerTableID = self.getRestrictionLayerTableID(currRestrictionLayer)
            idxRestrictionID = currRestriction.fieldNameIndex("RestrictionID")
            idxGeometryID = currRestriction.fieldNameIndex("GeometryID")

            if self.restrictionInProposal(currRestriction[idxRestrictionID], currRestrictionLayerTableID, currProposalID):

                # restriction already is part of the current proposal
                # simply make changes to the current restriction in the current layer
                QgsMessageLog.logMessage("In onSaveRestrictionDetails. Saving details straight from form." + str(currRestriction.attribute("GeometryID")),
                                         tag="TOMs panel")

                #res = dialog.save()
                status = currRestrictionLayer.updateFeature(currRestriction)
                status = dialog.attributeForm().save()

                """if res == True:
                    QgsMessageLog.logMessage("In onSaveRestrictionDetails. Form saved.",
                                             tag="TOMs panel")
                else:
                    QgsMessageLog.logMessage("In onSaveRestrictionDetails. Form NOT saved.",
                                             tag="TOMs panel")"""

            else:

                # restriction is NOT part of the current proposal

                # need to:
                #    - enter the restriction into the table RestrictionInProposals, and
                #    - make a copy of the restriction in the current layer (with the new details)

                # QgsMessageLog.logMessage("In onSaveRestrictionDetails. Adding restriction. ID: " + str(currRestriction.id()),
                #                         tag="TOMs panel")

                # Create a new feature using the current details

                idxOpenDate = currRestriction.fieldNameIndex("OpenDate")
                newRestrictionID = str(uuid.uuid4())

                if currRestriction[idxRestrictionID] is None:
                    # This is a feature that has just been created. It exists but doesn't have a GeometryID.

                    # Not quite sure what is happening here but think the following:
                    #  Feature does not yet exist, i.e., not saved to layer yet, so there is no id for it and can't use either feature or layer to save
                    #  So, need to continue to modify dialog value which will be eventually saved

                    dialog.attributeForm().changeAttribute("RestrictionID", newRestrictionID)

                    QgsMessageLog.logMessage(
                        "In onSaveRestrictionDetails. Adding new restriction. ID: " + str(currRestriction[idxRestrictionID]),
                        tag="TOMs panel")

                    status = self.addRestrictionToProposal(str(currRestriction[idxRestrictionID]), currRestrictionLayerTableID,
                                             currProposalID, ACTION_OPEN_RESTRICTION())  # Open = 1

                    QgsMessageLog.logMessage(
                        "In onSaveRestrictionDetails. Transaction Status 1: " + str(
                            restrictionTransaction.currTransactionGroup.modified()),
                        tag="TOMs panel")

                    status = dialog.attributeForm().save()  # this issues a commit on the transaction?
                    #dialog.accept()
                    #QgsMessageLog.logMessage("Form accepted", tag="TOMs panel")
                    QgsMessageLog.logMessage(
                        "In onSaveRestrictionDetails. Transaction Status 2: " + str(
                            restrictionTransaction.currTransactionGroup.modified()),
                        tag="TOMs panel")

                else:

                    # this feature was created before this session, we need to:
                    #  - close it in the RestrictionsInProposals table
                    #  - clone it in the current Restrictions layer (with a new GeometryID and no OpenDate)
                    #  - and then stop any changes to the original feature

                    # ************* need to discuss: seems that new has become old !!!

                    QgsMessageLog.logMessage(
                        "In onSaveRestrictionDetails. Closing existing restriction. ID: " + str(
                            currRestriction[idxRestrictionID]),
                        tag="TOMs panel")

                    status = self.addRestrictionToProposal(currRestriction[idxRestrictionID], currRestrictionLayerTableID,
                                             currProposalID, ACTION_CLOSE_RESTRICTION())  # Open = 1; Close = 2

                    newRestriction = QgsFeature(currRestriction)

                    # TODO: Rethink logic here and need to unwind changes ... without triggering rollBack ?? maybe attributeForm.setFeature()
                    #dialog.reject()

                    newRestriction[idxRestrictionID] = newRestrictionID
                    newRestriction[idxOpenDate] = None
                    newRestriction[idxGeometryID] = None
                    currRestrictionLayer.addFeatures([newRestriction])

                    QgsMessageLog.logMessage(
                        "In onSaveRestrictionDetails. Clone restriction. New ID: " + str(newRestriction[idxRestrictionID]),
                        tag="TOMs panel")

                    attrs2 = newRestriction.attributes()
                    QgsMessageLog.logMessage("In onSaveRestrictionDetails: clone Restriction: " + str(attrs2),
                        tag="TOMs panel")
                    QgsMessageLog.logMessage("In onSaveRestrictionDetails. Clone: {}".format(newRestriction.geometry().exportToWkt()),
                                             tag="TOMs panel")

                    status = self.addRestrictionToProposal(newRestriction[idxRestrictionID], currRestrictionLayerTableID,
                                             currProposalID, ACTION_OPEN_RESTRICTION())  # Open = 1; Close = 2

                    QgsMessageLog.logMessage(
                        "In onSaveRestrictionDetails. Opening clone. ID: " + str(
                            newRestriction[idxRestrictionID]),
                        tag="TOMs panel")

                    dialog.attributeForm().resetValues()

                pass

            # Now commit changes and redraw

            attrs1 = currRestriction.attributes()
            QgsMessageLog.logMessage("In onSaveRestrictionDetails: currRestriction: " + str(attrs1),
                                     tag="TOMs panel")
            QgsMessageLog.logMessage(
                "In onSaveRestrictionDetails. curr: {}".format(currRestriction.geometry().exportToWkt()),
                tag="TOMs panel")

            # Make sure that the saving will not be executed immediately, but
            # only when the event loop runs into the next iteration to avoid
            # problems

            QgsMessageLog.logMessage(
                "In onSaveRestrictionDetails. Transaction Status 3: " + str(
                    restrictionTransaction.currTransactionGroup.modified()),
                tag="TOMs panel")

            commitStatus = restrictionTransaction.commitTransactionGroup(currRestrictionLayer)
            #restrictionTransaction.deleteTransactionGroup()
            QgsMessageLog.logMessage(
                "In onSaveRestrictionDetails. Transaction Status 4: " + str(
                    restrictionTransaction.currTransactionGroup.modified()),
                tag="TOMs panel")
            # Trying to unset map tool to force updates ...
            #self.iface.mapCanvas().unsetMapTool(self.iface.mapCanvas().mapTool())
            #dialog.accept()
            """QgsMessageLog.logMessage(
                "In onSaveRestrictionDetails. Transaction Status 5: " + str(
                    restrictionTransaction.currTransactionGroup.modified()) + " commitStatus " + str(commitStatus),
                tag="TOMs panel")"""
            #status = dialog.attributeForm().close()
            #dialog.accept()
            #QTimer.singleShot(0, functools.partial(RestrictionTypeUtils.commitRestrictionChanges, currRestrictionLayer))

            status = dialog.reject()

        else:   # currProposal = 0, i.e., no change allowed

            """reply = QMessageBox.information(None, "Information",
                                            "Changes to current data are not allowed. Changes are made via Proposals",
                                            QMessageBox.Ok)"""
            status = dialog.reject()

        pass

        # ************* refresh the view. Might be able to set up a signal to get the proposals_panel to intervene

        QgsMessageLog.logMessage(
        "In onSaveRestrictionDetails. Finished",
        tag="TOMs panel")

        status = dialog.close()
        currRestrictionLayer.removeSelection()

        # reinstate Proposals Panel (if it needs it)
        #if not self.proposalPanel:
        self.proposalPanel = self.iface.mainWindow().findChild(QDockWidget, 'ProposalPanelDockWidgetBase')

        self.setupPanelTabs(self.iface, self.proposalPanel)
        #self.setupPanelTabs(self.iface, self.dock)

    def setDefaultRestrictionDetails(self, currRestriction, currRestrictionLayer):
        QgsMessageLog.logMessage("In setDefaultRestrictionDetails: ", tag="TOMs panel")

        generateGeometryUtils.setRoadName(currRestriction)
        if currRestrictionLayer.geometryType() == 1:  # Line or Bay
            generateGeometryUtils.setAzimuthToRoadCentreLine(currRestriction)

        currentCPZ, cpzWaitingTimeID = generateGeometryUtils.getCurrentCPZDetails(currRestriction)

        currRestriction.setAttribute("CPZ", currentCPZ)

        if currRestrictionLayer.name() == "Lines":
            currRestriction.setAttribute("RestrictionTypeID", 10)  # 10 = SYL (Lines) or Resident Permit Holders Bays (Bays)
            currRestriction.setAttribute("GeomShapeID", 10)   # 10 = Parallel Line

            currRestriction.setAttribute("NoWaitingTimeID", cpzWaitingTimeID)

        elif currRestrictionLayer.name() == "Bays":
            currRestriction.setAttribute("RestrictionTypeID", 28)  # 28 = Permit Holders Bays (Bays)
            currRestriction.setAttribute("GeomShapeID", 21)   # 21 = Parallel Bay (Polygon)

            currRestriction.setAttribute("TimePeriodID", cpzWaitingTimeID)

            currentPTA, ptaMaxStayID, ptaNoReturnTimeID = generateGeometryUtils.getCurrentPTADetails(currRestriction)

            currRestriction.setAttribute("MaxStayID", ptaMaxStayID)
            currRestriction.setAttribute("NoReturnID", ptaNoReturnTimeID)

        pass

    def updateRestriction(self, currRestrictionLayer, currRestrictionID, currAction, currProposalOpenDate):
        # update the Open/Close date for the restriction
        QgsMessageLog.logMessage("In updateRestriction. layer: " + str(
            currRestrictionLayer.name()) + " currRestId: " + currRestrictionID + " Opendate: " + str(
            currProposalOpenDate), tag="TOMs panel")

        # idxOpenDate = currRestrictionLayer.fieldNameIndex("OpenDate2")
        # idxCloseDate = currRestrictionLayer.fieldNameIndex("CloseDate2")

        # clear filter
        currRestrictionLayer.setSubsetString("")

        for currRestriction in currRestrictionLayer.getFeatures():
            #QgsMessageLog.logMessage("In updateRestriction. checkRestId: " + currRestriction.attribute("GeometryID"), tag="TOMs panel")

            if currRestriction.attribute("RestrictionID") == currRestrictionID:
                QgsMessageLog.logMessage(
                    "In updateRestriction. Action on: " + currRestrictionID + " Action: " + str(currAction),
                    tag="TOMs panel")
                if currAction == ACTION_OPEN_RESTRICTION():  # Open
                    statusUpd = currRestrictionLayer.changeAttributeValue(currRestriction.id(),
                                                              currRestrictionLayer.fieldNameIndex("OpenDate"),
                                                              currProposalOpenDate)
                    QgsMessageLog.logMessage(
                        "In updateRestriction. " + currRestrictionID + " Opened", tag="TOMs panel")
                else:  # Close
                    statusUpd = currRestrictionLayer.changeAttributeValue(currRestriction.id(),
                                                              currRestrictionLayer.fieldNameIndex("CloseDate"),
                                                              currProposalOpenDate)
                    QgsMessageLog.logMessage(
                        "In updateRestriction. " + currRestrictionID + " Closed", tag="TOMs panel")

                return statusUpd

        pass

    def setupRestrictionDialog(self, restrictionDialog, currRestrictionLayer, currRestriction, restrictionTransaction):

        #self.restrictionDialog = restrictionDialog
        #self.currRestrictionLayer = currRestrictionLayer
        #self.currRestriction = currRestriction
        #self.restrictionTransaction = restrictionTransaction

        if restrictionDialog is None:
            QgsMessageLog.logMessage(
                "In setupRestrictionDialog. dialog not found",
                tag="TOMs panel")

        restrictionDialog.attributeForm().disconnectButtonBox()
        button_box = restrictionDialog.findChild(QDialogButtonBox, "button_box")

        if button_box is None:
            QgsMessageLog.logMessage(
                "In setupRestrictionDialog. button box not found",
                tag="TOMs panel")

        button_box.accepted.disconnect(restrictionDialog.accept)
        button_box.accepted.connect(functools.partial(self.onSaveRestrictionDetails, currRestriction,
                                      currRestrictionLayer, restrictionDialog, restrictionTransaction))

        restrictionDialog.attributeForm().attributeChanged.connect(functools.partial(self.onAttributeChangedClass2, currRestriction, currRestrictionLayer))

        button_box.rejected.disconnect(restrictionDialog.reject)
        button_box.rejected.connect(functools.partial(self.onRejectRestrictionDetailsFromForm, restrictionDialog, restrictionTransaction))

        self.photoDetails(restrictionDialog, currRestrictionLayer, currRestriction)

        """def onSaveRestrictionDetailsFromForm(self):
        QgsMessageLog.logMessage("In onSaveRestrictionDetailsFromForm", tag="TOMs panel")
        self.onSaveRestrictionDetails(self.currRestriction,
                                      self.currRestrictionLayer, self.restrictionDialog, self.restrictionTransaction)"""

    def onRejectRestrictionDetailsFromForm(self, restrictionDialog, restrictionTransaction):
        QgsMessageLog.logMessage("In onRejectRestrictionDetailsFromForm", tag="TOMs panel")
        #self.currRestrictionLayer.destroyEditCommand()
        restrictionDialog.reject()

        #self.rollbackCurrentEdits()
        
        restrictionTransaction.rollBackTransactionGroup()
        
        # reinstate Proposals Panel (if it needs it)

        #if not self.proposalPanel:
        self.proposalPanel = self.iface.mainWindow().findChild(QDockWidget, 'ProposalPanelDockWidgetBase')

        self.setupPanelTabs(self.iface, self.proposalPanel)

    def onAttributeChangedClass2(self, currFeature, layer, fieldName, value):
        QgsMessageLog.logMessage(
            "In FormOpen:onAttributeChangedClass 2 - layer: " + str(layer.name()) + " (" + fieldName + "): " + str(value), tag="TOMs panel")

        # self.currRestriction.setAttribute(fieldName, value)
        try:

            currFeature[layer.fieldNameIndex(fieldName)] = value
            #currFeature.setAttribute(layer.fieldNameIndex(fieldName), value)

        except:

            reply = QMessageBox.information(None, "Error",
                                                "onAttributeChangedClass2. Update failed for: " + str(layer.name()) + " (" + fieldName + "): " + str(value),
                                                QMessageBox.Ok)  # rollback all changes
        return

    def photoDetails(self, dialog, currRestLayer, currRestrictionFeature):

        # Function to deal with photo fields

        QgsMessageLog.logMessage("In photoDetails", tag="TOMs panel")

        FIELD1 = dialog.findChild(QLabel, "Photo_Widget_01")
        FIELD2 = dialog.findChild(QLabel, "Photo_Widget_02")
        FIELD3 = dialog.findChild(QLabel, "Photo_Widget_03")

        path_absolute = QgsExpressionContextUtils.projectScope().variable('PhotoPath')
        if path_absolute == None:
            reply = QMessageBox.information(None, "Information", "Please set value for PhotoPath.", QMessageBox.Ok)
            return

        layerName = currRestLayer.name()

        # Generate the full path to the file

        fileName1 = layerName + "_Photos_01"
        fileName2 = layerName + "_Photos_02"
        fileName3 = layerName + "_Photos_03"

        idx1 = currRestLayer.fieldNameIndex(fileName1)
        idx2 = currRestLayer.fieldNameIndex(fileName2)
        idx3 = currRestLayer.fieldNameIndex(fileName3)

        QgsMessageLog.logMessage("In photoDetails. idx1: " + str(idx1) + "; " + str(idx2) + "; " + str(idx3),
                                 tag="TOMs panel")
        # if currRestrictionFeature[idx1]:
        # QgsMessageLog.logMessage("In photoDetails. photo1: " + str(currRestrictionFeature[idx1]), tag="TOMs panel")
        # QgsMessageLog.logMessage("In photoDetails. photo2: " + str(currRestrictionFeature.attribute(idx2)), tag="TOMs panel")
        # QgsMessageLog.logMessage("In photoDetails. photo3: " + str(currRestrictionFeature.attribute(idx3)), tag="TOMs panel")

        if FIELD1:
            QgsMessageLog.logMessage("In photoDetails. FIELD 1 exisits",
                                     tag="TOMs panel")
            if currRestrictionFeature[idx1]:
                newPhotoFileName1 = os.path.join(path_absolute, currRestrictionFeature[idx1])
            else:
                newPhotoFileName1 = None

            QgsMessageLog.logMessage("In photoDetails. A. Photo1: " + str(newPhotoFileName1), tag="TOMs panel")
            pixmap1 = QPixmap(newPhotoFileName1)
            if pixmap1.isNull():
                pass
                # FIELD1.setText('Picture could not be opened ({path})'.format(path=newPhotoFileName1))
            else:
                FIELD1.setPixmap(pixmap1)
                FIELD1.setScaledContents(True)
                QgsMessageLog.logMessage("In photoDetails. Photo1: " + str(newPhotoFileName1), tag="TOMs panel")

        if FIELD2:
            QgsMessageLog.logMessage("In photoDetails. FIELD 2 exisits",
                                     tag="TOMs panel")
            if currRestrictionFeature[idx2]:
                newPhotoFileName2 = os.path.join(path_absolute, currRestrictionFeature[idx2])
            else:
                newPhotoFileName2 = None

            # newPhotoFileName2 = os.path.join(path_absolute, str(currRestrictionFeature[idx2]))
            # newPhotoFileName2 = os.path.join(path_absolute, str(currRestrictionFeature.attribute(fileName2)))
            QgsMessageLog.logMessage("In photoDetails. A. Photo2: " + str(newPhotoFileName2), tag="TOMs panel")
            pixmap2 = QPixmap(newPhotoFileName2)
            if pixmap2.isNull():
                pass
                # FIELD1.setText('Picture could not be opened ({path})'.format(path=newPhotoFileName1))
            else:
                FIELD1.setPixmap(pixmap2)
                FIELD1.setScaledContents(True)
                QgsMessageLog.logMessage("In photoDetails. Photo2: " + str(newPhotoFileName2), tag="TOMs panel")

        if FIELD3:
            QgsMessageLog.logMessage("In photoDetails. FIELD 3 exisits",
                                     tag="TOMs panel")
            if currRestrictionFeature[idx3]:
                newPhotoFileName3 = os.path.join(path_absolute, currRestrictionFeature[idx3])
            else:
                newPhotoFileName3 = None

            # newPhotoFileName3 = os.path.join(path_absolute, str(currRestrictionFeature[idx3]))
            # newPhotoFileName3 = os.path.join(path_absolute,
            #                                 str(currRestrictionFeature.attribute(fileName3)))
            # newPhotoFileName3 = os.path.join(path_absolute, str(layerName + "_Photos_03"))
            pixmap3 = QPixmap(newPhotoFileName3)
            if pixmap3.isNull():
                pass
                # FIELD1.setText('Picture could not be opened ({path})'.format(path=newPhotoFileName1))
            else:
                FIELD1.setPixmap(pixmap3)
                FIELD1.setScaledContents(True)
                QgsMessageLog.logMessage("In photoDetails. Photo3: " + str(newPhotoFileName3), tag="TOMs panel")

        pass

    def onSaveProposalFormDetails(self, currProposal, proposalsDialog, proposalTransaction):
        QgsMessageLog.logMessage("In onSaveProposalFormDetails.", tag="TOMs panel")

        # proposalsLayer.startEditing()

        """def onSaveProposalDetails(self):
        QgsMessageLog.logMessage("In onSaveProposalFormDetails.", tag="TOMs panel")
        self.Proposals.startEditing()
        """

        #proposalsLayerfromClass = TOMsTableNames.PROPOSALS()
        #QgsMessageLog.logMessage("In onSaveProposalFormDetails. Proposals (class):" + str(proposalsLayerfromClass.name()), tag="TOMs panel")

        # set up field indexes
        idxProposalID = self.tableNames.PROPOSALS.fieldNameIndex("ProposalID")
        idxProposalTitle = self.tableNames.PROPOSALS.fieldNameIndex("ProposalTitle")
        idxProposalStatusID = self.tableNames.PROPOSALS.fieldNameIndex("ProposalStatusID")
        idxProposalNotes = self.tableNames.PROPOSALS.fieldNameIndex("ProposalNotes")
        idxProposalCreateDate = self.tableNames.PROPOSALS.fieldNameIndex("ProposalCreateDate")
        idxProposalOpenDate = self.tableNames.PROPOSALS.fieldNameIndex("ProposalOpenDate")

        QgsMessageLog.logMessage("In onSaveProposalFormDetails. currProposalStatus = " + str(currProposal[idxProposalStatusID]), tag="TOMs panel")

        #updateStatus = False
        newProposal = False

        if currProposal[idxProposalStatusID] == PROPOSAL_STATUS_ACCEPTED():  # 2 = accepted

            reply = QMessageBox.question(None, 'Confirm changes to Proposal',
                                         # How do you access the main window to make the popup ???
                                         'Are you you want to ACCEPT this proposal?. Accepting will make all the proposed changes permanent.',
                                         QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                # open the proposal - and accept any other changes to the form

                # currProposalID = currProposal[idxProposalID]

                # TODO: Need to check that this is an authorised user

                # Now close dialog
                updateStatus = proposalsDialog.accept()

                updateStatus = True

                if updateStatus == True:
                    currProposalID = currProposal[idxProposalID]
                    currOpenDate = currProposal[idxProposalOpenDate]
                    updateStatus = self.acceptProposal(currProposalID, currOpenDate)

                if updateStatus == True:
                    updateStatus = proposalsDialog.accept()
                    #proposalsDialog.close()
                else:
                    proposalsDialog.reject()

                # proposalAccepted.emit()

            else:
                proposalsDialog.reject()

        elif currProposal[idxProposalStatusID] == PROPOSAL_STATUS_REJECTED():  # 3 = rejected

            reply = QMessageBox.question(None, 'Confirm changes to Proposal',
                                         # How do you access the main window to make the popup ???
                                         'Are you you want to REJECT this proposal?. Accepting will make all the proposed changes permanent.',
                                         QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                # open the proposal - and accept any other changes to the form

                # currProposalID = currProposal[idxProposalID]

                # TODO: Need to check that this is an authorised user

                updateStatus = self.tableNames.PROPOSALS.updateFeature(currProposal)
                updateStatus = True

                if updateStatus == True:
                    self.rejectProposal(currProposal[idxProposalID])

                #proposalsDialog.accept()
                proposalsDialog.close()
                # proposalAccepted.emit()

            else:
                # proposalsDialog.reject ((currProposal[idxProposalID]))
                proposalsDialog.reject()

        else:

            QgsMessageLog.logMessage(
                "In onSaveProposalFormDetails. currProposalID = " + str(currProposal[idxProposalID]),
                tag="TOMs panel")

            # anything else can be saved.
            if currProposal[idxProposalID] == None:

                # This is a new proposal ...

                newProposal = True

                # add geometry
                #currProposal.setGeometry(QgsGeometry())

            """updateStatus = proposalsLayer.updateFeature(currProposal)

            QgsMessageLog.logMessage(
                "In onSaveProposalFormDetails. updateStatus = " + str(updateStatus),
                tag="TOMs panel")
            updateStatus = True"""

            proposalsDialog.accept()
            #proposalsDialog.close()
            #proposalsDialog.attributeForm().save()

        QgsMessageLog.logMessage("In onSaveProposalFormDetails. Before save. " + str(currProposal.attribute("ProposalTitle")) + " Status: " + str(currProposal.attribute("ProposalStatusID")), tag="TOMs panel")
        #QMessageBox.information(None, "Information", ("Just before Proposal save in onSaveProposalFormDetails"))

        #QgsMessageLog.logMessage("In onSaveProposalFormDetails. Saving: Proposals", tag="TOMs panel")

        # A little pause for the db to catch up
        """time.sleep(.1)

        res = proposalsLayer.commitChanges()
        QgsMessageLog.logMessage("In onSaveProposalFormDetails. Saving: Proposals. res: " + str(res), tag="TOMs panel")

        if res <> True:
            # save the active layer

            reply = QMessageBox.information(None, "Error",
                                            "Changes to " + proposalsLayer.name() + " failed: " + str(
                                                proposalsLayer.commitErrors()),
                                            QMessageBox.Ok)
        pass"""

        #ProposalTypeUtils.commitProposalChanges(proposalsLayer)

        # Make sure that the saving will not be executed immediately, but
        # only when the event loop runs into the next iteration to avoid
        # problems

        #self.Proposals.editCommandEnded.connect(self.proposalsManager.setCurrentProposal)

        # QTimer.singleShot(0, functools.partial(self.commitProposalChanges, proposalsLayer))
        # Trying to unset map tool to force updates ...
        self.iface.mapCanvas().unsetMapTool(self.iface.mapCanvas().mapTool())

        #self.commitProposalChanges()
        proposalTransaction.commitTransactionGroup(self.tableNames.PROPOSALS)
        #proposalTransaction.deleteTransactionGroup()

        #self.rollbackCurrentEdits()
        
        """if updateStatus == False:

            reply = QMessageBox.information(None, "Error",
                                            "Changes to " + proposalsLayer.name() + " failed: " + str(
                                                proposalsLayer.commitErrors()),
                                            QMessageBox.Ok)
        else:

            # set up action for when new proposal is created
            # self.Proposals.editingStopped.connect(self.createProposalcb)
            # self.Proposals.featureAdded.connect(self.proposalsManager.setCurrentProposal)
            self.Proposals.editCommandEnded.connect(self.proposalsManager.setCurrentProposal)

            #QTimer.singleShot(0, functools.partial(self.commitProposalChanges, proposalsLayer))
            self.commitProposalChanges(proposalsLayer)
        pass"""

        # For some reason the committedFeaturesAdded signal for layer "Proposals" is not firing at this point and so the cbProposals is not refreshing ...

        if newProposal == True:
            QgsMessageLog.logMessage("In onSaveProposalFormDetails. newProposalID = " + str(currProposal.id()), tag="TOMs panel")
            #self.proposalsManager.setCurrentProposal(currProposal[idxProposalID])
            #ProposalTypeUtils.iface.proposalChanged.emit()

            for proposal in self.tableNames.PROPOSALS.getFeatures():
                if proposal[idxProposalTitle] == currProposal[idxProposalTitle]:
                    QgsMessageLog.logMessage("In onSaveProposalFormDetails. newProposalID = " + str(proposal.id()),
                                             tag="TOMs panel")
                    newProposalID = proposal[idxProposalID]
                    #self.proposalsManager.setCurrentProposal(proposal[idxProposalID])

            self.proposalsManager.newProposalCreated.emit(newProposalID)

    def acceptProposal(self, currProposalID, currProposalOpenDate):
        QgsMessageLog.logMessage("In acceptProposal.", tag="TOMs panel")

        # Now loop through all the items in restrictionsInProposals for this proposal and take appropriate action

        RestrictionsInProposalsLayer = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionsInProposals")[0]
        idxProposalID = RestrictionsInProposalsLayer.fieldNameIndex("ProposalID")
        idxRestrictionTableID = RestrictionsInProposalsLayer.fieldNameIndex("RestrictionTableID")
        idxRestrictionID = RestrictionsInProposalsLayer.fieldNameIndex("RestrictionID")
        idxActionOnProposalAcceptance = RestrictionsInProposalsLayer.fieldNameIndex("ActionOnProposalAcceptance")

        # restrictionFound = False

        # not sure if there is better way to search for something, .e.g., using SQL ??

        statusUpd = True

        for restrictionInProposal in RestrictionsInProposalsLayer.getFeatures():
            if restrictionInProposal.attribute("ProposalID") == currProposalID:
                currRestrictionLayer = self.getRestrictionsLayerFromID(restrictionInProposal.attribute("RestrictionTableID"))
                currRestrictionID = restrictionInProposal.attribute("RestrictionID")
                currAction = restrictionInProposal.attribute("ActionOnProposalAcceptance")

                #currRestrictionLayer.startEditing()

                """if not currRestrictionLayer.isEditable():
                    currRestrictionLayer.startEditing()"""

                statusUpd = self.updateRestriction(currRestrictionLayer, currRestrictionID, currAction, currProposalOpenDate)

                if statusUpd == False:
                    reply = QMessageBox.information(None, "Error",
                                                    "Changes to " + currRestrictionLayer.name() + " failed: " + str(
                                                        currRestrictionLayer.commitErrors()), QMessageBox.Ok)
                    return statusUpd

        return statusUpd

    def rejectProposal(self, currProposalID):
        QgsMessageLog.logMessage("In rejectProposal.", tag="TOMs panel")

        # This is a "reset" so change all open/close dates back to null. **** Need to be careful if a restriction is in more than one proposal

        # Now loop through all the items in restrictionsInProposals for this proposal and take appropriate action

        RestrictionsInProposalsLayer = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionsInProposals")[0]
        idxProposalID = RestrictionsInProposalsLayer.fieldNameIndex("ProposalID")
        idxRestrictionTableID = RestrictionsInProposalsLayer.fieldNameIndex("RestrictionTableID")
        idxRestrictionID = RestrictionsInProposalsLayer.fieldNameIndex("RestrictionID")
        idxActionOnProposalAcceptance = RestrictionsInProposalsLayer.fieldNameIndex("ActionOnProposalAcceptance")

        # restrictionFound = False

        # not sure if there is better way to search for something, .e.g., using SQL ??

        for restrictionInProposal in RestrictionsInProposalsLayer.getFeatures():
            if restrictionInProposal.attribute("ProposalID") == currProposalID:
                currRestrictionLayer = self.getRestrictionsLayerFromID(restrictionInProposal.attribute("RestrictionTableID"))
                currRestrictionID = restrictionInProposal.attribute("RestrictionID")
                currAction = restrictionInProposal.attribute("ActionOnProposalAcceptance")

                #currRestrictionLayer.startEditing()
                """if not currRestrictionLayer.isEditable():
                    currRestrictionLayer.startEditing()"""

                statusUpd = self.updateRestriction(currRestrictionLayer, currRestrictionID, currAction, None)

            pass

        pass

        #def commitProposalChanges(self):
        # Function to save changes to current layer and to RestrictionsInProposal
        #pass

        """QgsMessageLog.logMessage("In commitProposalChanges: ", tag="TOMs panel")

        # save changes to all layers

        localTrans = TOMsTransaction(self.iface)

        localTrans.prepareLayerSet()
        setLayers = localTrans.layersInTransaction()

        modifiedTransaction = self.currTransaction.modified()

        for layerID in setLayers:

            transLayer = QgsMapLayerRegistry.instance().mapLayer(layerID)
            QgsMessageLog.logMessage("In commitProposalChanges. Considering: " + transLayer.name(), tag="TOMs panel")

            commitStatus = transLayer.commitChanges()
            commitErrors = transLayer.commitErrors()

            if commitErrors:
                reply = QMessageBox.information(None, "Error",
                                            "Changes to " + transLayer.name() + " failed: " + str(
                                                transLayer.commitErrors()), QMessageBox.Ok)
            break

        statusTrans = False
        errMessage = str()

        # setup signal catch
        #currTransaction.commitError.disconnect()
        self.currTransaction.commitError.connect(self.showTransactionErrorMessage)

        #try:

        #statusTrans = proposalsLayer.commitChanges()
        #commitErrors = proposalsLayer.commitErrors()


        self.currTransaction.commitError.disconnect()
        self.currTransaction = None
        self.rollbackCurrentEdits()

        # TODO: deal with errors in Transaction

        return"""

        """except:

            reply = QMessageBox.information(None, "Error",
                                                "Proposal changes failed: " + str(errMessage),
                                                QMessageBox.Ok)  # rollback all changes

            if currTransaction.rollback(errMessage) == False:
                reply = QMessageBox.information(None, "Error",
                                                "Proposal rollback failed: " + str(errMessage),
                                                QMessageBox.Ok)  # rollback all changes"""

        """def createProposalTransactionGroup(self, tableNames):

        self.tableNames = tableNames
        # Function to create group of layers to be in Transaction for changing proposal

        QgsMessageLog.logMessage("In createProposalTransactionGroup: ", tag="TOMs panel")
        #QMessageBox.information(None, "Information", ("Entering commitRestrictionChanges"))

        # save changes to all layers

        #RestrictionsLayers = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionLayers")[0]

        idxRestrictionsLayerName = self.tableNames.RESTRICTIONLAYERS.fieldNameIndex("RestrictionLayerName")
        idxRestrictionsLayerID = self.tableNames.RESTRICTIONLAYERS.fieldNameIndex("id")

        # create transaction
        #newTransaction = QgsTransaction("Test1")

        #QgsMessageLog.logMessage("In createProposalTransactionGroup. Adding ProposalsLayer ", tag="TOMs panel")
        self.setTransactionGroup = [self.tableNames.PROPOSALS.id()]

        self.setTransactionGroup.append(self.tableNames.RESTRICTIONS_IN_PROPOSALS.id())
        self.setTransactionGroup.append(self.tableNames.BAYS.id())
        QgsMessageLog.logMessage("In createProposalTransactionGroup. SUCCESS Adding RestrictionsInProposals Layer ",
                                 tag="TOMs panel")

        for layer in self.tableNames.RESTRICTIONLAYERS.getFeatures():

            currRestrictionLayerName = layer[idxRestrictionsLayerName]

            restrictionLayer = QgsMapLayerRegistry.instance().mapLayersByName(currRestrictionLayerName)[0]

            self.setTransactionGroup.append(restrictionLayer.id())
            QgsMessageLog.logMessage("In createProposalTransactionGroup. SUCCESS Adding " + str(restrictionLayer.name()), tag="TOMs panel")


        newTransaction = QgsTransaction.create(self.setTransactionGroup)


        if not newTransaction.supportsTransaction(self.tableNames.RESTRICTIONS_IN_PROPOSALS):
            QgsMessageLog.logMessage("In createProposalTransactionGroup. ERROR Adding RestrictionsInProposals Layer ",
                                     tag="TOMs panel")
        else:
            setTransactionGroup.append(self.tableNames.RESTRICTIONS_IN_PROPOSALS.id())
            QgsMessageLog.logMessage("In createProposalTransactionGroup. SUCCESS Adding RestrictionsInProposals Layer ",
                                     tag="TOMs panel")

        for layerID in self.setTransactionGroup:

            #currRestrictionLayerName = layer[idxRestrictionsLayerName]

            transLayer = QgsMapLayerRegistry.instance().mapLayer(layerID)


            caps_string = transLayer.capabilitiesString()
            QgsMessageLog.logMessage("In createProposalTransactionGroup: " + str(transLayer.name()) + ": capabilities: " + caps_string,
                                     tag="TOMs panel")

            statusSupp = newTransaction.supportsTransaction(transLayer)
            if not newTransaction.supportsTransaction(transLayer):
                QgsMessageLog.logMessage("In createProposalTransactionGroup. ERROR Adding " + str(transLayer.name()),
                                         tag="TOMs panel")
            else:
                QgsMessageLog.logMessage("In createProposalTransactionGroup. SUCCESS Adding " + str(transLayer.name()), tag="TOMs panel")


        return newTransaction"""

    def showTransactionErrorMessage(self):

        QgsMessageLog.logMessage("In showTransactionErrorMessage: ", tag="TOMs panel")

        """reply = QMessageBox.information(None, "Error",
                                        "Proposal changes failed: " + str(errMsg),
                                        QMessageBox.Ok)  # rollback all changes"""

    def rollbackCurrentEdits(self):
        # Function to rollback any changes to the tables that might have changes

        QgsMessageLog.logMessage("In rollbackCurrentEdits: ", tag="TOMs panel")

        # rollback changes to all layers

        proposalsLayer = QgsMapLayerRegistry.instance().mapLayersByName("Proposals")[0]
        RestrictionsInProposalLayer = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionsInProposals")[0]
        RestrictionsLayers = QgsMapLayerRegistry.instance().mapLayersByName("RestrictionLayers")[0]

        idxRestrictionsLayerName = RestrictionsLayers.fieldNameIndex("RestrictionLayerName")
        idxRestrictionsLayerID = RestrictionsLayers.fieldNameIndex("id")

        # create transaction
        #newTransaction = QgsTransaction("Test1")

        QgsMessageLog.logMessage("In rollbackCurrentEdits. ProposalsLayer ", tag="TOMs panel")

        if proposalsLayer.editBuffer():
            statusRollback = proposalsLayer.rollBack()

        if RestrictionsInProposalLayer.editBuffer():
            statusRollback = RestrictionsInProposalLayer.rollBack()

        for layer in RestrictionsLayers.getFeatures():

            currRestrictionLayerName = layer[idxRestrictionsLayerName]

            restrictionLayer = QgsMapLayerRegistry.instance().mapLayersByName(currRestrictionLayerName)[0]

            QgsMessageLog.logMessage("In rollbackCurrentEdits. " + str(restrictionLayer.name()), tag="TOMs panel")
            if restrictionLayer.editBuffer():
                statusRollback = restrictionLayer.rollBack()

        return

    def getLookupDescription(self, lookupLayer, code):

        #QgsMessageLog.logMessage("In getLookupDescription", tag="TOMs panel")

        query = "\"Code\" = " + str(code)
        request = QgsFeatureRequest().setFilterExpression(query)

        #QgsMessageLog.logMessage("In getLookupDescription. queryStatus: " + str(query), tag="TOMs panel")

        for row in lookupLayer.getFeatures(request):
            #QgsMessageLog.logMessage("In getLookupDescription: found row " + str(row.attribute("Description")), tag="TOMs panel")
            return row.attribute("Description") # make assumption that only one row

        return None

    def setupPanelTabs(self, iface, parent):

        # https: // gis.stackexchange.com / questions / 257603 / activate - a - panel - in -tabbed - panels?utm_medium = organic & utm_source = google_rich_qa & utm_campaign = google_rich_qa

        dws = iface.mainWindow().findChildren(QDockWidget)
        #parent = iface.mainWindow().findChild(QDockWidget, 'ProposalPanel')
        dockstate = iface.mainWindow().dockWidgetArea(parent)
        for d in dws:
            if d is not parent:
                if iface.mainWindow().dockWidgetArea(d) == dockstate and d.isHidden() == False:
                    iface.mainWindow().tabifyDockWidget(parent, d)
        parent.raise_()

    def prepareRestrictionForEdit(self, currRestriction, currRestrictionLayer):

        QgsMessageLog.logMessage("In prepareRestrictionForEdit",
                                 tag="TOMs panel")

        # if required, clone the current restriction and enter details into "RestrictionsInProposals" table

        newFeature = currRestriction

        idxRestrictionID = currRestrictionLayer.fieldNameIndex("RestrictionID")

        if not self.restrictionInProposal(currRestriction[idxRestrictionID], self.getRestrictionLayerTableID(currRestrictionLayer), self.proposalsManager.currentProposal()):
            QgsMessageLog.logMessage("In prepareRestrictionForEdit - adding details to RestrictionsInProposal", tag="TOMs panel")
            #  This one is not in the current Proposal, so now we need to:
            #  - generate a new ID and assign it to the feature for which the geometry has changed
            #  - switch the geometries arround so that the original feature has the original geometry and the new feature has the new geometry
            #  - add the details to RestrictionsInProposal

            newFeature = self.cloneRestriction(currRestriction, currRestrictionLayer)

            # Check to see if the feature is added
            QgsMessageLog.logMessage("In TOMsNodeTool:cloneRestriction - feature exists in layer - " + newFeature.attribute("RestrictionID"), tag="TOMs panel")

            # Add details to "RestrictionsInProposals"

            self.addRestrictionToProposal(currRestriction[idxRestrictionID],
                                          self.getRestrictionLayerTableID(currRestrictionLayer),
                                          self.proposalsManager.currentProposal(),
                                          ACTION_CLOSE_RESTRICTION())  # close the original feature
            QgsMessageLog.logMessage("In TOMsNodeTool:cloneRestriction - feature closed.", tag="TOMs panel")

            self.addRestrictionToProposal(newFeature[idxRestrictionID], self.getRestrictionLayerTableID(currRestrictionLayer),
                                          self.proposalsManager.currentProposal(),
                                          ACTION_OPEN_RESTRICTION())  # open the new one
            QgsMessageLog.logMessage("In TOMsNodeTool:cloneRestriction - feature opened.", tag="TOMs panel")


        else:

            QgsMessageLog.logMessage("In TOMsNodeTool:init - restriction exists in RestrictionsInProposal", tag="TOMs panel")
            #newFeature = currRestriction

        # test to see if the geometry is correct
        #self.restrictionTransaction.commitTransactionGroup(self.origLayer)

        return newFeature

    def onFeatureAdded(self, fid):
        QgsMessageLog.logMessage("In onFeatureAdded - newFid: " + str(fid),
                                 tag="TOMs panel")
        self.newFid = fid

    def cloneRestriction(self, originalFeature, restrictionLayer):

        QgsMessageLog.logMessage("In TOMsNodeTool:cloneRestriction",
                                 tag="TOMs panel")
        #  This one is not in the current Proposal, so now we need to:
        #  - generate a new ID and assign it to the feature for which the geometry has changed
        #  - switch the geometries arround so that the original feature has the original geometry and the new feature has the new geometry
        #  - add the details to RestrictionsInProposal

        #originalFeature = self.origFeature.getFeature()

        newFeature = QgsFeature(originalFeature)

        #newFeature.setAttributes(originalFeature.attributes())

        newRestrictionID = str(uuid.uuid4())

        idxRestrictionID = restrictionLayer.fieldNameIndex("RestrictionID")
        idxOpenDate = restrictionLayer.fieldNameIndex("OpenDate")
        idxGeometryID = restrictionLayer.fieldNameIndex("GeometryID")

        newFeature[idxRestrictionID] = newRestrictionID
        newFeature[idxOpenDate] = None
        newFeature[idxGeometryID] = None

        #abstractGeometry = originalFeature.geometry().geometry().clone()  # make a deep copy of the geometry ... https://gis.stackexchange.com/questions/232056/how-to-deep-copy-a-qgis-memory-layer

        #newFeature.setGeometry(QgsGeometry(originalFeature.geometry()))
        #geomStatus = restrictionLayer.changeGeometry(newFeature.id(), QgsGeometry(abstractGeometry))

        # if a new feature has been added to the layer, the featureAdded signal is emitted by the layer ... and the fid is obtained
        # self.newFid = None
        restrictionLayer.featureAdded.connect(self.onFeatureAdded)

        addStatus = restrictionLayer.addFeature(newFeature, True)
        #addStatus = restrictionLayer.addFeatures([newFeature], True)

        restrictionLayer.featureAdded.disconnect(self.onFeatureAdded)

        restrictionLayer.updateExtents()
        restrictionLayer.updateFields()

        QgsMessageLog.logMessage("In TOMsNodeTool:cloneRestriction - addStatus: " + str(addStatus) + " featureID: " + str(self.newFid), #+ " geomStatus: " + str(geomStatus),
                                 tag="TOMs panel")

        QgsMessageLog.logMessage("In TOMsNodeTool:cloneRestriction - attributes: (fid=" + str(newFeature.id()) + ") " + str(newFeature.attributes()),
                                 tag="TOMs panel")

        QgsMessageLog.logMessage("In TOMsNodeTool:cloneRestriction - newGeom: " + newFeature.geometry().exportToWkt(),
                                 tag="TOMs panel")

        # test to see that feature has been added ...
        #feat = restrictionLayer.getFeatures(QgsFeatureRequest(newFeature.id())).next()
        feat = restrictionLayer.getFeatures(
            QgsFeatureRequest().setFilterExpression('GeometryID = \'{}\''.format(newFeature['GeometryID']))).next()

        """originalGeomBuffer = QgsGeometry(originalfeature.geometry())
        QgsMessageLog.logMessage(
            "In TOMsNodeTool:cloneRestriction - originalGeom: " + originalGeomBuffer.exportToWkt(),
            tag="TOMs panel")
        self.origLayer.changeGeometry(currRestriction.id(), originalGeomBuffer)

        QgsMessageLog.logMessage("In TOMsNodeTool:cloneRestriction - geometries switched.", tag="TOMs panel")"""

        return newFeature

