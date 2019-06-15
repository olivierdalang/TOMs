# -----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# ---------------------------------------------------------------------
# Tim Hancock 2017

## Incorporates InstantPrintPlugin from Sandro Mani / Sourcepole AG

# -*- coding: latin1 -*-
# Import the PyQt and QGIS libraries

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *

from TOMs.InstantPrint.TOMsInstantPrintTool import TOMsInstantPrintTool

class labelsToolBar():

    def __init__(self, iface, TOMsLabelsToolBar, proposalsManager):

        QgsMessageLog.logMessage("In labelsToolBar", tag="TOMs panel")
        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.TOMsLabelsToolBar = TOMsLabelsToolBar
        self.proposalsManager = proposalsManager

        #self.tool = TOMsInstantPrintTool(self.iface, self.proposalsManager)

        self.initLabelsToolBar()


        # https: // gis.stackexchange.com / questions / 244584 / adding - textbox - to - qgis - plugin - toolbar

    def initLabelsToolBar(self):
        
        QgsMessageLog.logMessage("In initLabelsToolBar:", tag="TOMs panel")

        # Create actions
        self.actionCreateLabel = QAction(QIcon(":/plugins/TOMs/resources/CreateConstructionLine.svg"),
                               QCoreApplication.translate("MyPlugin", "Create label"),
                               self.iface.mainWindow())
        self.actionCreateLabel.setCheckable(True)

        self.actionMoveLabel = QAction(QIcon(":/plugins/TOMs/resources/CreateConstructionLine.svg"),
                               QCoreApplication.translate("MyPlugin", "Move label"),
                               self.iface.mainWindow())
        self.actionMoveLabel.setCheckable(True)

        self.actionLinkLabelToRestriction = QAction(QIcon(":/plugins/TOMs/resources/CreateConstructionLine.svg"),
                               QCoreApplication.translate("MyPlugin", "Link label to restriction"),
                               self.iface.mainWindow())
        self.actionLinkLabelToRestriction.setCheckable(True)

        self.actionBreakLinkBetweenLabelAndRestriction = QAction(QIcon(":/plugins/TOMs/resources/CreateConstructionLine.svg"),
                               QCoreApplication.translate("MyPlugin", "Break link between label and restriction"),
                               self.iface.mainWindow())
        self.actionBreakLinkBetweenLabelAndRestriction.setCheckable(True)

        # Add actions to the toolbar
        self.TOMsLabelsToolBar.addAction(self.actionCreateLabel)
        self.TOMsLabelsToolBar.addAction(self.actionMoveLabel)
        self.TOMsLabelsToolBar.addAction(self.actionLinkLabelToRestriction)
        self.TOMsLabelsToolBar.addAction(self.actionBreakLinkBetweenLabelAndRestriction)

        # Connect action signals to slots
        self.actionCreateLabel.triggered.connect(self.doCreateLabel)
        self.actionMoveLabel.triggered.connect(self.doMoveLabel)
        self.actionLinkLabelToRestriction.triggered.connect(self.doLinkLabelToRestriction)
        self.actionBreakLinkBetweenLabelAndRestriction.triggered.connect(self.doBreakLinkBetweenLabelAndRestriction)

    def enableLabelsToolBar(self):
        QgsMessageLog.logMessage("In enableLabelsToolBar", tag="TOMs panel")

        self.actionCreateLabel.setEnabled(True)
        self.actionMoveLabel.setEnabled(True)
        self.actionLinkLabelToRestriction.setEnabled(True)
        self.actionBreakLinkBetweenLabelAndRestriction.setEnabled(True)

    def disableLabelsToolBar(self):
        QgsMessageLog.logMessage("In disableLabelsToolBar", tag="TOMs panel")

        self.actionCreateLabel.setEnabled(False)
        self.actionMoveLabel.setEnabled(False)
        self.actionLinkLabelToRestriction.setEnabled(False)
        self.actionBreakLinkBetweenLabelAndRestriction.setEnabled(False)

    def doCreateLabel(self):

        """
        Logic is:
            ensure that restriction is selected
            Start Transaction (if not current)
            generate appropriate label, i.e., work out type (colour, etc) and text (from lookup??)
            position (perhaps horizontal in the middle of the restriction. It can then be moved.
            Commit ...

        """
        QgsMessageLog.logMessage("In doCreateLabel", tag="TOMs panel")

        #self.proposalsManager.TOMsToolChanged.emit()

        # Get the current proposal from the session variables
        currProposalID = self.proposalsManager.currentProposal()

        if currProposalID == 0:
            # Ensure that no updates can occur for Proposal = 0
            self.restrictionTransaction.rollBackTransactionGroup()  # stop any editing
            return

        self.restrictionTransaction.startTransactionGroup()  # start editing

        currRestrictionLayer = self.iface.activeLayer()

        if not currRestrictionLayer:

            reply = QMessageBox.information(self.iface.mainWindow(), "Information",
                                            "Select restriction first and then choose information button",
                                            QMessageBox.Ok)
            return

        QgsMessageLog.logMessage("In doCreateLabel. currLayer: " + str(currRestrictionLayer.name() + " Nr feats: " + str(currRestrictionLayer.selectedFeatureCount())), tag="TOMs panel")

        if currRestrictionLayer.selectedFeatureCount() > 0:


            selectedRestrictions = currRestrictionLayer.selectedFeatures()
            for currRestriction in selectedRestrictions:
                #self.restrictionForm = BayRestrictionForm(currRestrictionLayer, currRestriction)
                #self.restrictionForm.show()

                # now create label

                if not self.createLabel(currRestriction, currRestrictionLayer, currProposalID,
                                        self.proposalsManager, self.restrictionTransaction):
                    reply = QMessageBox.information(self.iface.mainWindow(), "Error",
                                                    "Problem creating label",
                                                    QMessageBox.Ok)
                    return

                QgsMessageLog.logMessage(
                        "In doCreateLabel. currRestrictionLayer: " + str(currRestrictionLayer.name()),
                        tag="TOMs panel")

        # TODO: Check behaviour for multiple select ...


    def doMoveLabel(self):
        QgsMessageLog.logMessage("In doMoveLabel", tag="TOMs panel")

        """
        Logic is:
         - select label and drag. Save inside maptool ??
        """

        self.mapTool = labelTool(self.iface, self.proposalsManager, self.restrictionTransaction)

        self.mapTool.setAction(self.actionMoveLabel)
        self.iface.mapCanvas().setMapTool(self.mapTool)

    def doLinkLabelToRestriction(self):
        QgsMessageLog.logMessage("In doLinkLabelToRestriction", tag="TOMs panel")

        """
        Logic is:
            ensure that restriction is selected
            Start Transaction (if not current)
            select label and set up links
            Commit ...

        """

        # self.proposalsManager.TOMsToolChanged.emit()

        # Get the current proposal from the session variables
        currProposalID = self.proposalsManager.currentProposal()

        if currProposalID == 0:
            # Ensure that no updates can occur for Proposal = 0
            self.restrictionTransaction.rollBackTransactionGroup()  # stop any editing
            return

        self.restrictionTransaction.startTransactionGroup()  # start editing

        currRestrictionLayer = self.iface.activeLayer()

        if not currRestrictionLayer:
            reply = QMessageBox.information(self.iface.mainWindow(), "Information",
                                            "Select restriction first ... ",
                                            QMessageBox.Ok)
            return

        QgsMessageLog.logMessage("In doLinkLabelToRestriction. currLayer: " + str(
            currRestrictionLayer.name() + " Nr feats: " + str(currRestrictionLayer.selectedFeatureCount())),
                                 tag="TOMs panel")

        if currRestrictionLayer.selectedFeatureCount() > 0:

            selectedRestrictions = currRestrictionLayer.selectedFeatures()
            for currRestriction in selectedRestrictions:
                # self.restrictionForm = BayRestrictionForm(currRestrictionLayer, currRestriction)
                # self.restrictionForm.show()

                # now select label

                label = self.selectLabel()

                if not label:
                    reply = QMessageBox.information(self.iface.mainWindow(), "Error",
                                                    "Problem creating label",
                                                    QMessageBox.Ok)
                    return

                QgsMessageLog.logMessage(
                    "In doLinkLabelToRestriction. currRestrictionLayer: " + str(currRestrictionLayer.name()),
                    tag="TOMs panel")

                # Now create linkages
                self.linkRestrictionAndLabel(currRestriction, currRestrictionLayer, currProposalID, label,
                                        self.proposalsManager, self.restrictionTransaction)
                # TODO: Check behaviour for multiple select ...

    def doBreakLinkBetweenLabelAndRestriction(self):
        QgsMessageLog.logMessage("In doBreakLinkBetweenLabelAndRestriction", tag="TOMs panel")

        """
        Logic is:
            ensure that restriction is selected
            Start Transaction (if not current)
            select label and confirm break
            Check whether or not there are any other restrictions connected to label
            If not, delete
            Commit ...

        """

        # self.proposalsManager.TOMsToolChanged.emit()

        # Get the current proposal from the session variables
        currProposalID = self.proposalsManager.currentProposal()

        if currProposalID == 0:
            # Ensure that no updates can occur for Proposal = 0
            self.restrictionTransaction.rollBackTransactionGroup()  # stop any editing
            return

        self.restrictionTransaction.startTransactionGroup()  # start editing

        currRestrictionLayer = self.iface.activeLayer()

        if not currRestrictionLayer:
            reply = QMessageBox.information(self.iface.mainWindow(), "Information",
                                            "Select restriction first and then choose label",
                                            QMessageBox.Ok)
            return

        QgsMessageLog.logMessage("In doBreakLinkBetweenLabelAndRestriction. currLayer: " + str(
            currRestrictionLayer.name() + " Nr feats: " + str(currRestrictionLayer.selectedFeatureCount())),
                                 tag="TOMs panel")

        if currRestrictionLayer.selectedFeatureCount() > 0:

            selectedRestrictions = currRestrictionLayer.selectedFeatures()
            for currRestriction in selectedRestrictions:
                # self.restrictionForm = BayRestrictionForm(currRestrictionLayer, currRestriction)
                # self.restrictionForm.show()

                label = self.selectLabel()

                if not label:
                    reply = QMessageBox.information(self.iface.mainWindow(), "Error",
                                                    "Problem creating label",
                                                    QMessageBox.Ok)
                    return

                QgsMessageLog.logMessage(
                    "In doLinkLabelToRestriction. currRestrictionLayer: " + str(currRestrictionLayer.name()),
                    tag="TOMs panel")

                # Now create linkages
                self.breakLinkBetweenLabelAndRestriction(currRestriction, currRestrictionLayer, currProposalID, label,
                                        self.proposalsManager, self.restrictionTransaction)
                # TODO: Check behaviour for multiple select ...


    def createLabel (self, currRestriction, currRestrictionLayer, currProposalID,
                     proposalsManager, restrictionTransaction):

        # Find centre point of restriction
        labelPoint = self.getCentreOfRestriction (currRestriction)

        # Work out characteristics of layer, i.e., what information is required in label and what colours
        labelTypes = self.getLabelTypes(currRestrictionLayer)  # NB: there could be multiple types here, e.g., waiting and loading
        # labelTypes could be list ??

        # Create ...
        for labelType in labelTypes:   # will also need to know iteration so can generate offsets
            self.makeLabel(currRestriction, labelPoint, labelType)

        return True

    def getLabelTypes(self, restrictionLayer):
        # given current restriction layer, search LABEL_TYPES to get types associated with layer ...

        pass

    def makeLabel(self, currRestriction, labelPoint, labelType, currProposalID,
                  proposalsManager, restrictionTransaction):
        # from the currentRestriction, pick up text for LabelType

        labelText = self.getLabelText(currRestriction, labelType)

        labelID = self.addLabel(labelPoint, labelType, labelText, currProposalID,
                  proposalsManager, restrictionTransaction)

        status = linkRestrictionAndLabel(currRestriction, currRestrictionLayer, currProposalID, labelID,
                                 proposalsManager, restrictionTransaction)

        # TODO: Need to create the leader ...
        self.createLeaderForLabel(currRestriction, labelID)

        status = self.addLabelToProposal(currRestriction, labelID, currProposalID,
                  proposalsManager, restrictionTransaction)


    def addLabel(self, labelPoint, labelType, labelText, currProposalID,
                  proposalsManager, restrictionTransaction):
        labelID = 0
        # add feature to LABELS layer
        QgsMessageLog.logMessage("In addLabel.", tag="TOMs panel")

        newLabel = QgsFeature(self.LABELS.fields())
        newLabel.setGeometry(labelPoint.geometry())

        idxRestrictionID = newLabel.fieldNameIndex("RestrictionID")
        #idxGeometryID = currRestriction.fieldNameIndex("GeometryID")
        idxCurrentUser = newLabel.fieldNameIndex("Surveyor")

        # may need to add specific X, Y fields to symbolise ??

        # set up attributes
        #newLabel
        newRestrictionID = str(uuid.uuid4())

        newLabel[idxRestrictionID] = newRestrictionID
        #newLabel[idxOpenDate] = None
        #newLabel[idxGeometryID] = None

        # Add create date and user details - user currentUser and date
        # newRestriction[idxCurrentUser] = self.currentUser()
        # newRestriction[idxCreateDateTime] = self.date()

        self.LABELS.addFeatures([newLabel])

        QgsMessageLog.logMessage(
            "In addLabel. Before record create. RestrictionID: " + str(newRestrictionID),
            tag="TOMs panel")

        #attrs = newRestrictionsInProposal.attributes()

        # QMessageBox.information(None, "Information", ("addRestrictionToProposal" + str(attrs)))

        #returnStatus = RestrictionsInProposalsLayer.addFeatures([newRestrictionsInProposal])

        return returnStatus

        return labelID

    def addLabelForRestrictionToProposal(self, currRestrictionID, labelID, currProposalID,
                  proposalsManager, restrictionTransaction):
        # add details into RestrictionsInProposal
        restrictionWithlabelsTableID = getRestrictionLayerTableID(self, self.RESTRICTIONS_WITH_LABELS)
        status = addRestrictionToProposal(currRestrictionID, restrictionWithlabelsTableID, currProposalID, ACTION_OPEN_RESTRICTION())
        pass

    def linkRestrictionAndLabel(self, currRestrictionID, currRestrictionLayer, currProposalID, labelID,
                                 proposalsManager, restrictionTransaction):

        # Add label/restriction details to RESTRICTIONS_WITH_LABELS

        newLabelForRestriction = QgsFeature(self.RESTRICTIONS_WITH_LABELS.fields())

        idxLabelForRestrictionID = newLabelForRestriction.fieldNameIndex("LabelForRestrictionID")
        #idxGeometryID = currRestriction.fieldNameIndex("GeometryID")
        idxCurrentUser = newLabelForRestriction.fieldNameIndex("Surveyor")
        idxRestrictionID = newLabelForRestriction.fieldNameIndex("RestrictionID")
        idxLabelID = newLabelForRestriction.fieldNameIndex("LabelID")
        idxLastUpdateDateTime = newLabelForRestriction.fieldNameIndex("LastUpdateDateTime")  # Need to change db fro this??

        # set up attributes
        newLabelForRestrictionID = str(uuid.uuid4())

        newLabelForRestriction[idxLabelForRestrictionID] = newLabelForRestrictionID
        #newLabelForRestriction[idxOpenDate] = None
        #newLabelForRestriction[idxGeometryID] = None
        newLabelForRestriction[idxCurrentUser] = self.currentUser()
        newLabelForRestriction[idxRestrictionID] = currRestrictionID
        newLabelForRestriction[idxLabelID] = labelID
        newLabelForRestriction[idxLastUpdateDateTime] = self.datetime()

        # Add create date and user details - user currentUser and date
        # newRestriction[idxCurrentUser] = self.currentUser()
        # newRestriction[idxCreateDateTime] = self.date()

        self.RESTRICTIONS_WITH_LABELS.addFeatures([newLabelForRestriction])

        QgsMessageLog.logMessage(
            "In linkRestrictionAndLabel. Before record create. newLabelForRestrictionID: " + str(newLabelForRestrictionID),
            tag="TOMs panel")

        pass

    def breakLinkBetweenLabelAndRestriction(self):
        pass

    def getLabelText(self, currRestriction, labelType):
        # get the relevant text for the label

        if currRestriction(restType) < 100:
            # bay type ...
            try:
                # QgsMessageLog.logMessage("In getBayTimePeriodLabelText:", tag="TOMs panel")

                maxStayText, noReturnText, timePeriodText = generateGeometryUtils.getBayRestrictionLabelText(feature)

            except:
                QgsMessageLog.logMessage('getBayTimePeriodLabelText', tag="TOMs panel")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                QgsMessageLog.logMessage(
                    'getBayTimePeriodLabelText: error in expression function: ' + str(
                        repr(traceback.extract_tb(exc_traceback))),
                    tag="TOMs panel")

            labelText = ''  # generate ...

        elif currRestriction(restType) < 200:
            try:
                waitingText, loadingText = generateGeometryUtils.getWaitingLoadingRestrictionLabelText(feature)
            except:
                QgsMessageLog.logMessage('getWaitingRestrictionLabelText', tag="TOMs panel")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                QgsMessageLog.logMessage(
                    'getWaitingRestrictionLabelText: error in expression function: ' + str(
                        repr(traceback.extract_tb(exc_traceback))),
                    tag="TOMs panel")

                # QgsMessageLog.logMessage("In getWaitingRestrictionLabelText ****:" + " Waiting: " + str(waitingText) + " Loading: " + str(loadingText), tag="TOMs panel")
                # waitingText = "Test"
            if waitingText:
                labelText = "No Waiting: " + waitingText
                labelText = waitingText

        elif currRestriction(restType) < 300:
            pass

        ### TO DO: Not sure what else ??

        return None

        pass
